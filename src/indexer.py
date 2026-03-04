"""
indexer.py — Indexing orchestration for the code-intel MCP server.

Provides:
    _hash_file            : Compute SHA-256 digest of a file.
    _should_process_file  : Scope-filter a file against include/exclude globs.
    refresh_index_impl    : Two-pass indexing orchestrator (definitions → links).
"""

import os
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional

from fnmatch import fnmatch

from .config import IGNORE_DIRS, SUPPORTED_EXTENSIONS
from .git_utils import batch_get_git_info
from .utils import normalize_path
from .context import AppContext

logger = logging.getLogger("server")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _hash_file(filepath: str) -> str:
    """Compute SHA-256 hash of a file. Returns empty string on failure."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash file {filepath}: {e}")
        return ""


def _should_process_file(
    filepath: str,
    project_root: str,
    include: Optional[str],
    exclude: Optional[str],
) -> bool:
    """Determine if a file should be processed based on include/exclude patterns.

    Path matching is done relative to *project_root* so that globs such as
    ``'src/api/**'`` work regardless of where the server is launched from.
    """
    rel_path = os.path.relpath(filepath, project_root).replace(os.path.sep, "/")

    # 1. System ignores (hard rules)
    for ignored in IGNORE_DIRS:
        if ignored in rel_path.split("/"):
            return False

    # 2. Exclude patterns (highest priority)
    if exclude and fnmatch(rel_path, exclude):
        return False

    # 3. Include patterns (selective mode)
    if include:
        return fnmatch(rel_path, include)

    return True


# ---------------------------------------------------------------------------
# Two-pass indexing orchestrator
# ---------------------------------------------------------------------------

async def refresh_index_impl(
    root_path: str = ".",
    force_full_scan: bool = False,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
    ctx: AppContext = None,
    inference_semaphore: asyncio.Semaphore = None,
    file_semaphore: asyncio.Semaphore = None,
) -> str:
    """Scan *root_path*, index definitions (Pass 1), then link usages (Pass 2).

    Args:
        root_path:          Absolute path to the project root.
        force_full_scan:    Wipe existing index before re-indexing.
        include:            Optional glob to ONLY index matching files.
        exclude:            Optional glob to SKIP matching files.
        ctx:                Shared service container (AppContext).
        inference_semaphore: Limits concurrent embedding requests.
        file_semaphore:     Limits concurrent file-processing coroutines.
    """
    project_root_str = normalize_path(root_path)
    root = Path(project_root_str)
    if not root.exists():
        return f"Error: Path {root} does not exist."

    if force_full_scan:
        ctx.vector_store.clear_project(project_root_str)
        ctx.knowledge_graph.clear()

    initial_count = ctx.vector_store.count_chunks(project_root_str)
    existing_hashes = {} if force_full_scan else ctx.vector_store.get_project_hashes(project_root_str)

    stats = {
        "files_scanned": 0,
        "chunks_indexed": 0,
        "errors": 0,
        "initial_count": initial_count,
        "skipped": 0,
    }

    files_to_process = []
    files_to_skip = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.startswith("."):
                continue
            file_path = Path(dirpath) / f
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                file_str = normalize_path(str(file_path))

                if not _should_process_file(file_str, project_root_str, include, exclude):
                    continue

                current_hash = _hash_file(file_str)
                stored_hash = existing_hashes.get(file_str)

                if not force_full_scan and stored_hash == current_hash:
                    files_to_skip.append(file_str)
                else:
                    files_to_process.append((file_str, current_hash))

    if not files_to_process and not files_to_skip:
        return "No supported code files found matching your criteria."

    stats["files_scanned"] = len(files_to_process) + len(files_to_skip)
    stats["skipped"] = len(files_to_skip)

    if not files_to_process:
        return (
            f"Indexing Complete (All {stats['skipped']} files unchanged).\n"
            f"Total Chunks in Index: {initial_count}"
        )

    just_filepaths = [f[0] for f in files_to_process]
    git_info = await batch_get_git_info(just_filepaths, project_root_str)

    parse_cache = {}

    # --- Pass 1: Index definitions & generate embeddings ---
    async def process_file_pass1(filepath: str, file_hash: str):
        try:
            chunks = ctx.parser.parse_file(filepath, project_root=project_root_str)
            if not chunks:
                return 0
            
            parse_cache[filepath] = chunks

            file_git = git_info.get(filepath, {"author": None, "last_modified": None})
            for chunk in chunks:
                chunk.author = file_git.get("author")
                chunk.last_modified = file_git.get("last_modified")
                chunk.content_hash = file_hash

            texts = [f"{c.language} {c.type} {c.symbol_name}: {c.content}" for c in chunks]
            embeddings = await ctx.ollama.get_embeddings_batch(texts, semaphore=inference_semaphore)

            if embeddings:
                ctx.vector_store.upsert_chunks(project_root_str, chunks, embeddings)

            return len(chunks)
        except Exception as e:
            logger.error(f"Pass 1 (Indexing) failed for {filepath}: {e}")
            return 0

    async def process_file_bounded_pass1(file_data):
        filepath, file_hash = file_data
        async with file_semaphore:
            return await process_file_pass1(filepath, file_hash)

    logger.info("Starting Pass 1: Indexing Definitions...")
    tasks_p1 = [process_file_bounded_pass1(fd) for fd in files_to_process]
    results_p1 = await asyncio.gather(*tasks_p1)
    stats["chunks_indexed"] = sum(results_p1)

    # --- Pass 2: Link usages ---
    # All Pass 1 definitions must be committed before we resolve edges.
    async def process_file_pass2(filepath: str):
        try:
            chunks = parse_cache.get(filepath)
            if chunks is None:
                chunks = ctx.parser.parse_file(filepath, project_root=project_root_str)
                
            if not chunks:
                return
            for chunk in chunks:
                ctx.linker.link_chunk_usages(project_root_str, chunk)
        except Exception as e:
            logger.error(f"Pass 2 (Linking) failed for {filepath}: {e}")

    async def process_file_bounded_pass2(file_data):
        filepath, _ = file_data
        async with file_semaphore:
            await process_file_pass2(filepath)

    logger.info("Starting Pass 2: Linking Usages...")
    tasks_p2 = [process_file_bounded_pass2(fd) for fd in files_to_process]
    await asyncio.gather(*tasks_p2)

    final_count = ctx.vector_store.count_chunks(project_root_str)
    scan_type = "Full Rebuild" if force_full_scan else "Incremental Update"
    return (
        f"Indexing Complete for project: {project_root_str}\n"
        f"Scan Type: {scan_type}\n"
        f"Files Scanned: {stats['files_scanned']} ({stats['skipped']} skipped)\n"
        f"Total Chunks in Index: {final_count}"
    )
