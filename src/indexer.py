"""Structural refresh orchestration for the rebooted code-intel server."""

import os
import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

from fnmatch import fnmatch

from .config import IGNORE_DIRS, SUPPORTED_EXTENSIONS
from .utils import normalize_path
from .context import AppContext

logger = logging.getLogger("server")


def _format_elapsed_time(seconds: float) -> str:
    """Format wall-clock runtime for user-facing refresh responses."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


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


def _get_file_state(filepath: str) -> Optional[dict]:
    """Return lightweight file metadata used for manifest-based change detection."""
    try:
        stat_result = os.stat(filepath)
        return {
            "size": int(stat_result.st_size),
            "mtime_ns": int(stat_result.st_mtime_ns),
        }
    except OSError:
        return None


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


async def refresh_index_impl(
    root_path: str = ".",
    force_full_scan: bool = False,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
    ctx: AppContext = None,
    inference_semaphore: asyncio.Semaphore = None,
    file_semaphore: asyncio.Semaphore = None,
) -> str:
    """Scan *root_path* and persist structural facts into the new core.

    Args:
        root_path:          Absolute path to the project root.
        force_full_scan:    Wipe existing index before re-indexing.
        include:            Optional glob to ONLY index matching files.
        exclude:            Optional glob to SKIP matching files.
        ctx:                Shared service container (AppContext).
        inference_semaphore: Unused compatibility parameter.
        file_semaphore:     Unused compatibility parameter.
    """
    start_time = time.perf_counter()
    project_root_str = normalize_path(root_path)
    root = Path(project_root_str)
    if not root.exists():
        return f"Error: Path {root} does not exist."

    candidate_files = []

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

                candidate_files.append(file_str)

    structural_result = ctx.structural_refresher.refresh(
        project_root_str,
        candidate_files,
        force_full_scan=force_full_scan,
        prune_missing_files=include is None and exclude is None,
    )

    project_stats = ctx.structural_store.get_project_stats(project_root_str) or {
        "tracked_files": 0,
        "symbol_count": 0,
        "import_count": 0,
        "edge_count": 0,
    }

    if not candidate_files and structural_result.files_removed == 0 and project_stats["tracked_files"] == 0:
        return "No supported code files found matching your criteria."

    if not structural_result.changed_files and not structural_result.removed_files:
        elapsed = _format_elapsed_time(time.perf_counter() - start_time)
        return (
            f"Indexing Complete (All {structural_result.files_skipped} files unchanged).\n"
            f"Tracked Files: {project_stats['tracked_files']}\n"
            f"Indexed Symbols: {project_stats['symbol_count']}\n"
            f"Indexed Imports: {project_stats['import_count']}\n"
            f"Elapsed Time: {elapsed}"
        )

    scan_type = "Full Structural Refresh" if force_full_scan else "Incremental Structural Update"
    elapsed = _format_elapsed_time(time.perf_counter() - start_time)
    return (
        f"Indexing Complete for project: {project_root_str}\n"
        f"Scan Type: {scan_type}\n"
        f"Files Scanned: {structural_result.files_scanned} ({structural_result.files_skipped} skipped)\n"
        f"Files Changed: {len(structural_result.changed_files)}\n"
        f"Files Removed: {structural_result.files_removed}\n"
        f"Tracked Files: {project_stats['tracked_files']}\n"
        f"Indexed Symbols: {project_stats['symbol_count']}\n"
        f"Indexed Imports: {project_stats['import_count']}\n"
        f"Elapsed Time: {elapsed}"
    )
