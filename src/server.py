import sys
import logging
import asyncio
import os
from pathlib import Path
from typing import List
from fastmcp import FastMCP

# --- STDOUT FORTRESS ---
# MCP uses stdout for protocol communication.
# We monkeypatch print to ensure any library calls go to stderr instead.
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

# Configure logging to file (not stdout!)
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

# Semaphore to control concurrency for embedding generation
EMBEDDING_SEMAPHORE = asyncio.Semaphore(5) 

@mcp.tool()
async def refresh_index(root_path: str = ".", force_full_scan: bool = False) -> str:
    """
    Scans the workspace, parses code, generates embeddings, and updates the local vector index.
    The index is isolated to this specific project root.
    
    Args:
        root_path: The root directory to scan/index.
        force_full_scan: If True, re-indexes everything.
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path {root} does not exist."
    
    project_root_str = str(root)

    # Handle Force Full Scan
    if force_full_scan:
        logger.info(f"Force full scan requested for {project_root_str}. Clearing index.")
        vector_store.clear_project(project_root_str)

    # Initial stats
    initial_count = vector_store.count_chunks(project_root_str)
    stats = {
        "files_scanned": 0, 
        "chunks_indexed": 0, 
        "errors": 0,
        "initial_count": initial_count
    }
    
    # 1. Discovery
    files_to_process = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and d != ".cognee_vault" and not d.startswith(".")]
        
        for f in filenames:
            if f.startswith("."): continue
            file_path = Path(dirpath) / f
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_to_process.append(str(file_path))

    if not files_to_process:
        return "No supported code files found."

    # 2. Processing 
    async def process_file(filepath: str):
        try:
            chunks = parser.parse_file(filepath)
            if not chunks:
                return 0
            
            texts = [c.content for c in chunks]
            
            async with EMBEDDING_SEMAPHORE:
                embeddings = await ollama_client.get_embeddings_batch(texts)
            
            if embeddings:
                # Target the specific project table
                vector_store.upsert_chunks(project_root_str, chunks, embeddings)
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return e

    tasks = [process_file(f) for f in files_to_process]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for r in results:
        if isinstance(r, int):
            stats["chunks_indexed"] += r
        else:
            stats["errors"] += 1
            
    stats["files_scanned"] = len(files_to_process)
    
    final_count = vector_store.count_chunks(project_root_str)
    
    return (
        f"Indexing Complete for project: {project_root_str}\n"
        f"Operation: {'Full Rebuild' if force_full_scan else 'Incremental Update'}\n"
        f"Files Scanned: {stats['files_scanned']}\n"
        f"Chunks Added/Updated: {stats['chunks_indexed']}\n"
        f"Total Chunks in Index: {final_count} (Delta: {final_count - stats['initial_count']})\n"
        f"Errors: {stats['errors']}"
    )

@mcp.tool()
async def search_code(query: str, root_path: str = ".", limit: int = 10) -> str:
    """
    Semantically searches the codebase for the given query, isolated to the current project.
    
    Args:
        query: Semantic search query.
        root_path: The project root to search within.
    """
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)

        # Get query embedding
        query_vec = await ollama_client.get_embedding(query)
        
        # Search the isolated project DB
        results = vector_store.search(project_root_str, query_vec, limit=limit)
        
        if not results:
            return f"No matching code found in project: {project_root_str}"
            
        output = [f"Results for project: {project_root_str}\n"]
        for r in results:
            score_info = f" (Distance: {r.get('_distance', 'N/A'):.4f})" if '_distance' in r else ""
            output.append(
                f"File: {r['filename']} (Lines {r['start_line']}-{r['end_line']}){score_info}\n"
                f"Type: {r['type']}\n"
                f"Content:\n```\n{r['content']}\n```\n"
            )
            
        return "\n---\n".join(output)
        
    except Exception as e:
        return f"Search failed: {e}"

@mcp.tool()
async def get_stats(root_path: str = ".") -> str:
    """
    Returns the current indexing statistics for a project without modifying the index.
    
    Args:
        root_path: The project root to check.
    """
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)
        
        count = vector_store.count_chunks(project_root_str)
        
        if count == 0:
             return f"No index found for project: {project_root_str}\nStatus: Not Indexed"
             
        return (
            f"code-intel Stats for: {project_root_str}\n"
            f"----------------------------------------\n"
            f"Total Chunks: {count}\n"
            f"Status: Active"
        )
    except Exception as e:
        return f"Failed to get stats: {e}"

if __name__ == "__main__":
    mcp.run()
