import sys
import logging
import asyncio
import os
import builtins
import traceback
from pathlib import Path
from typing import List
from fastmcp import FastMCP

# --- STDOUT FORTRESS ---
import builtins
_original_print = builtins.print

def safe_print(*args, **kwargs):
    if 'file' not in kwargs or kwargs['file'] is None or kwargs['file'] == sys.stdout:
        kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)

builtins.print = safe_print

from .config import IGNORE_DIRS, SUPPORTED_EXTENSIONS, LOG_DIR
from .parser import CodeParser
from .embeddings import OllamaClient
from .storage import VectorStore
from .git_utils import batch_get_git_info

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "server.log", encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("server")

# Initialize components
mcp = FastMCP("Lightweight Code Intel")
parser = CodeParser()
ollama_client = OllamaClient()
vector_store = VectorStore()

# Semaphores
INFERENCE_SEMAPHORE = asyncio.Semaphore(5)
FILE_PROCESSING_SEMAPHORE = asyncio.Semaphore(10)

async def refresh_index_impl(root_path: str = ".", force_full_scan: bool = False) -> str:
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path {root} does not exist."
    project_root_str = str(root)

    if force_full_scan:
        vector_store.clear_project(project_root_str)

    initial_count = vector_store.count_chunks(project_root_str)
    stats = {"files_scanned": 0, "chunks_indexed": 0, "errors": 0, "initial_count": initial_count}
    
    files_to_process = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.startswith("."): continue
            file_path = Path(dirpath) / f
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_to_process.append(str(file_path))

    if not files_to_process:
        return "No supported code files found."

    git_info = await batch_get_git_info(files_to_process, project_root_str)

    async def process_file(filepath: str):
        try:
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks: return 0
            file_git = git_info.get(filepath, {"author": None, "last_modified": None})
            for chunk in chunks:
                chunk.author = file_git.get("author")
                chunk.last_modified = file_git.get("last_modified")
            texts = [f"{c.language} {c.type} {c.symbol_name}: {c.content}" for c in chunks]
            embeddings = await ollama_client.get_embeddings_batch(texts, semaphore=INFERENCE_SEMAPHORE)
            if embeddings:
                vector_store.upsert_chunks(project_root_str, chunks, embeddings)
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return 0

    async def process_file_bounded(f):
        async with FILE_PROCESSING_SEMAPHORE:
            return await process_file(f)

    tasks = [process_file_bounded(f) for f in files_to_process]
    results = await asyncio.gather(*tasks)
    stats["chunks_indexed"] = sum(results)
    stats["files_scanned"] = len(files_to_process)
    
    final_count = vector_store.count_chunks(project_root_str)
    scan_type = "Full Rebuild" if force_full_scan else "Incremental Update"
    return (
        f"Indexing Complete for project: {project_root_str}\n"
        f"Scan Type: {scan_type}\n"
        f"Files Scanned: {stats['files_scanned']}\n"
        f"Total Chunks in Index: {final_count}"
    )

@mcp.tool()
async def refresh_index(root_path: str = ".", force_full_scan: bool = False) -> str:
    return await refresh_index_impl(root_path, force_full_scan)

async def search_code_impl(query: str, root_path: str = ".", limit: int = 10) -> str:
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)
        query_vec = await ollama_client.get_embedding(query)
        results = vector_store.search(project_root_str, query_vec, limit=limit)
        if not results: return f"No matching code found in project: {project_root_str}"
        output = [f"Results for project: {project_root_str}\n"]
        for r in results:
            meta = []
            if r.get('author'): meta.append(f"Author: {r['author']}")
            if r.get('last_modified'): meta.append(f"Date: {r['last_modified']}")
            if r.get('dependencies') and r['dependencies'] != "[]": meta.append(f"Deps: {r['dependencies']}")
            
            meta_str = "\n".join(meta) + "\n" if meta else ""
            output.append(f"File: {r['filename']} ({r['start_line']}-{r['end_line']})\nSymbol: {r.get('symbol_name', 'N/A')}\nComplexity: {r.get('complexity', 0)}\n{meta_str}Content:\n```\n{r['content']}\n```\n")
        return "\n---\n".join(output)
    except Exception as e:
        return f"Search failed: {e}"

@mcp.tool()
async def search_code(query: str, root_path: str = ".", limit: int = 10) -> str:
    return await search_code_impl(query, root_path, limit)

@mcp.tool()
async def get_stats(root_path: str = ".") -> str:
    return await get_stats_impl(root_path)

async def get_stats_impl(root_path: str = ".") -> str:
    """Provides architectural insights."""
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)
        if vector_store is None: return "Error: Vector store not initialized."
        
        # LanceDB stats retrieval (synchronous - robust against threading issues)
        stats = vector_store.get_detailed_stats(project_root_str)
        
        if not stats: return f"No index found for project: {project_root_str}"
        
        lang_breakdown = "\n".join([f"  - {lang}: {count} chunks" for lang, count in stats["languages"].items()])
        summary = (
            f"Stats for: {project_root_str}\n"
            f"Total Chunks:     {stats['chunk_count']}\n"
            f"Unique Files:     {stats['file_count']}\n"
            f"Avg Complexity:   {stats['avg_complexity']:.2f}\n"
            f"Max Complexity:   {stats['max_complexity']}\n"
            f"Languages:\n{lang_breakdown}"
        )

        hubs = "\n".join([f"  - {h['file']} ({h['count']} imports)" for h in stats.get("dependency_hubs", [])[:5]])
        test_gaps = "\n".join([f"  - {g['symbol']} ({g['complexity']}) in {Path(g['file']).name}" for g in stats.get("test_gaps", [])[:5]])
        
        # Active branch retrieval
        from .git_utils import get_active_branch
        branch = await get_active_branch(project_root_str)
        
        pulse = f"\n\nProject Pulse:\n  - Active Branch: {branch}\n  - Stale Files:   {stats.get('stale_files_count', 0)}"
        return f"{summary}\n\nDependency Hubs:\n{hubs}\n\nTest Gaps:\n{test_gaps}{pulse}"
    except Exception as e:
        logger.error(f"get_stats failed: {e}\n{traceback.format_exc()}")
        return f"Failed to get stats: {e}"

if __name__ == "__main__":
    mcp.run()
