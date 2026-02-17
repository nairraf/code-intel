import sys
import logging
import asyncio
import os
import builtins
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
from .git_utils import batch_get_git_info


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
logger.debug("server.py: logging configured")


# Initialize components
logger.debug("server.py: initializing FastMCP")
mcp = FastMCP("Lightweight Code Intel")
logger.debug("server.py: initializing CodeParser")
parser = CodeParser()
logger.debug("server.py: initializing OllamaClient")
ollama_client = OllamaClient()
logger.debug("server.py: initializing VectorStore")
vector_store = VectorStore()
logger.debug("server.py: all globals initialized")

logger.debug("server.py: all globals initialized")

# Semaphores for concurrency control
# Global limit for Ollama requests across all files
INFERENCE_SEMAPHORE = asyncio.Semaphore(5)
# Limit for concurrent file processing
FILE_PROCESSING_SEMAPHORE = asyncio.Semaphore(10)


async def refresh_index_impl(root_path: str = ".", force_full_scan: bool = False) -> str:
    logger.debug(f"Entered refresh_index with root_path={root_path}, force_full_scan={force_full_scan}")
    """
    Scans the workspace, intelligently parses code using Tree-sitter, and updates the local vector index.
    
    Generates high-fidelity metadata including:
    - Symbol hierarchy (Classes, Functions, Methods)
    - Full signatures and docstrings
    - Cyclomatic complexity scores
    - Dependency mapping (imports/requires)
    - Language detection
    - Git authorship and modification history
    
    Args:
        root_path: The root directory to scan/index.
        force_full_scan: If True, wipes the existing index for this project and rebuilds.
    """
    logger.debug(f"refresh_index: resolving root_path {root_path}")
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

    # 1.5. Git metadata batch fetch
    logger.debug(f"Fetching git metadata for {len(files_to_process)} files...")
    git_info = await batch_get_git_info(files_to_process, project_root_str)
    logger.debug("Git metadata fetch complete.")

    # 2. Processing
    git_found_count = 0
    def _build_embedding_text(chunk):
        prefix_parts = [chunk.language, chunk.type]
        if chunk.symbol_name:
            prefix_parts.append(chunk.symbol_name)
        prefix = " ".join(prefix_parts)
        return f"{prefix}: {chunk.content}"

    async def process_file(filepath: str):
        try:
            logger.debug(f"Parsing file: {filepath}")
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks:
                logger.debug(f"No chunks parsed from: {filepath}")
                return 0
            # Attach git metadata
            file_git = git_info.get(filepath, {"author": None, "last_modified": None})
            if file_git.get("author"):
                nonlocal git_found_count
                git_found_count += 1
            for chunk in chunks:
                chunk.author = file_git.get("author")
                chunk.last_modified = file_git.get("last_modified")
            texts = [_build_embedding_text(c) for c in chunks]
            logger.debug(f"Requesting embeddings for {len(texts)} chunks from file: {filepath}")
            
            # The client uses the shared semaphore for throttling
            embeddings = await ollama_client.get_embeddings_batch(texts, semaphore=INFERENCE_SEMAPHORE)
            
            logger.debug(f"Received embeddings for file: {filepath}")
            if embeddings:
                vector_store.upsert_chunks(project_root_str, chunks, embeddings)
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return e

    async def process_file_bounded(f):
        async with FILE_PROCESSING_SEMAPHORE:
            return await process_file(f)

    tasks = [process_file_bounded(f) for f in files_to_process]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, int):
            stats["chunks_indexed"] += r
        else:
            stats["errors"] += 1
    stats["files_scanned"] = len(files_to_process)
    logger.info(f"Indexing summary: {stats['files_scanned']} files scanned, Git info found for {git_found_count} files.")
    
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
async def refresh_index(root_path: str = ".", force_full_scan: bool = False) -> str:
    return await refresh_index_impl(root_path, force_full_scan)

async def search_code_impl(query: str, root_path: str = ".", limit: int = 10) -> str:
    """
    Semantically searches for code while providing architectural insights.
    
    Returns high-fidelity metadata for each match:
    - Architectural Insights: Complexity scores and Signature analysis.
    - Context: Symbol hierarchy, Language detection, and Docstrings.
    - Relationships: Import-based dependency mapping and Related Tests.
    - Git History: Authorship and last modified timestamps.
    
    Args:
        query: Semantic search query (e.g., "how is authentication handled?").
        root_path: The project root to search within.
        limit: Number of results to return.
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
            symbol_info = ""
            if r.get("symbol_name"):
                symbol_info = f"Symbol: {r['symbol_name']}"
                if r.get("parent_symbol"):
                    symbol_info += f" (in {r['parent_symbol']})"
                symbol_info += "\n"
            sig_info = f"Signature: {r['signature']}\n" if r.get("signature") else ""
            lang_info = f"Language: {r['language']}\n" if r.get("language") else ""
            doc_info = f"Docstring: {r['docstring']}\n" if r.get("docstring") else ""
            author_info = f"Author: {r['author']}" if r.get("author") else ""
            modified_info = f" | Modified: {r['last_modified']}" if r.get("last_modified") else ""
            git_line = f"{author_info}{modified_info}\n" if author_info else ""
            deps_info = f"Dependencies: {r.get('dependencies', '[]')}\n" if r.get("dependencies") and r.get("dependencies") != "[]" else ""
            comp_info = f"Complexity: {r.get('complexity', 0)}\n"
            tests_info = f"Related Tests: {r.get('related_tests', '[]')}\n" if r.get("related_tests") and r.get("related_tests") != "[]" else ""
            output.append(
                f"File: {r['filename']} (Lines {r['start_line']}-{r['end_line']}){score_info}\n"
                f"{symbol_info}"
                f"{sig_info}"
                f"{lang_info}"
                f"{doc_info}"
                f"{git_line}"
                f"{deps_info}"
                f"{comp_info}"
                f"{tests_info}"
                f"Content:\n```\n{r['content']}\n```\n"
            )
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
    """
    Provides "God Mode" architectural insights:
    - Total chunks and unique files currently indexed.
    - Language breakdown across the codebase.
    - Top 5 High-Risk Symbols based on cyclomatic complexity.
    - Top 5 Dependency Hubs (Connectivity) to identify central components.
    - Test Gap Analysis identifying high-complexity symbols without related tests.
    - Project Pulse (Active Branch and Stale Files count).
    """
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)
        
        stats = vector_store.get_detailed_stats(project_root_str)
        
        if not stats:
             return f"No index found for project: {project_root_str}\nStatus: Not Indexed"
             
        lang_breakdown = "\n".join([f"  - {lang}: {count} chunks" for lang, count in stats["languages"].items()])
        
        final_summary = (
            f"code-intel High-Fidelity Stats for: {project_root_str}\n"
            f"{'-' * 60}\n"
            f"Status:           Active\n"
            f"Total Chunks:     {stats['chunk_count']}\n"
            f"Unique Files:     {stats['file_count']}\n"
            f"Avg Complexity:   {stats['avg_complexity']:.2f}\n"
            f"Max Complexity:   {stats['max_complexity']}\n\n"
            f"Language Breakdown:\n{lang_breakdown}"
        )

        # 1. High Risk Symbols
        high_risk_str = ""
        if stats.get("high_risk_symbols"):
            high_risk_str = "\n\nTop 5 High-Risk Symbols (Complexity):\n"
            high_risk_str += "\n".join([f"  - {s['symbol']} ({s['complexity']}) in {Path(s['file']).name}" for s in stats["high_risk_symbols"]])

        # 2. Dependency Hubs
        dep_hubs_str = ""
        if stats.get("dependency_hubs"):
            dep_hubs_str = "\n\nTop 5 Dependency Hubs (Connectivity):\n"
            dep_hubs_str += "\n".join([f"  - {h['file']} ({h['count']} imports)" for h in stats["dependency_hubs"]])

        # 3. Test Gaps
        test_gaps_str = ""
        if stats.get("test_gaps"):
            test_gaps_str = "\n\nTest Gaps (High Complexity, No Tests):\n"
            test_gaps_str += "\n".join([f"  - {g['symbol']} ({g['complexity']}) in {Path(g['file']).name}" for g in stats["test_gaps"]])

        # 4. Project Pulse
        from .git_utils import get_active_branch
        branch = await get_active_branch(project_root_str)
        stale_files = stats.get("stale_files_count", 0)
        pulse_str = (
            f"\n\nProject Pulse:\n"
            f"  - Active Branch: {branch}\n"
            f"  - Stale Files:   {stale_files} (not touched in 30+ days)"
        )

        return final_summary + high_risk_str + dep_hubs_str + test_gaps_str + pulse_str
    except Exception as e:
        return f"Failed to get stats: {e}"

if __name__ == "__main__":
    mcp.run()
