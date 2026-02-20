import sys
import logging
import asyncio
import os
import builtins
import traceback
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from fastmcp import FastMCP

# --- STDOUT FORTRESS ---
_original_print = builtins.print

def safe_print(*args, **kwargs):
    if 'file' not in kwargs or kwargs['file'] is None or kwargs['file'] == sys.stdout:
        kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)

from .config import IGNORE_DIRS, SUPPORTED_EXTENSIONS, LOG_DIR
from .parser import CodeParser
from .embeddings import OllamaClient
from .storage import VectorStore
from .git_utils import batch_get_git_info
from .knowledge_graph import KnowledgeGraph
from .linker import SymbolLinker

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
knowledge_graph = KnowledgeGraph()
linker = SymbolLinker(vector_store, knowledge_graph)

# Semaphores
INFERENCE_SEMAPHORE = asyncio.Semaphore(5)
FILE_PROCESSING_SEMAPHORE = asyncio.Semaphore(10)

def _hash_file(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash file {filepath}: {e}")
        return ""

async def refresh_index_impl(root_path: str = ".", force_full_scan: bool = False) -> str:
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path {root} does not exist."
    project_root_str = root.as_posix()

    if force_full_scan:
        vector_store.clear_project(project_root_str)
        knowledge_graph.clear()

    initial_count = vector_store.count_chunks(project_root_str)
    existing_hashes = {} if force_full_scan else vector_store.get_project_hashes(project_root_str)
    
    stats = {"files_scanned": 0, "chunks_indexed": 0, "errors": 0, "initial_count": initial_count, "skipped": 0}
    
    files_to_process = []
    files_to_skip = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.startswith("."): continue
            file_path = Path(dirpath) / f
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                file_str = file_path.resolve().as_posix()
                current_hash = _hash_file(file_str)
                
                stored_hash = existing_hashes.get(file_str)
                
                if not force_full_scan and stored_hash == current_hash:
                    files_to_skip.append(file_str)
                else:
                    files_to_process.append((file_str, current_hash))

    if not files_to_process and not files_to_skip:
        return "No supported code files found."

    stats["files_scanned"] = len(files_to_process) + len(files_to_skip)
    stats["skipped"] = len(files_to_skip)

    if not files_to_process:
        return (
            f"Indexing Complete (All {stats['skipped']} files unchanged).\n"
            f"Total Chunks in Index: {initial_count}"
        )

    # Process only files that changed
    # Process only files that changed
    just_filepaths = [f[0] for f in files_to_process]
    git_info = await batch_get_git_info(just_filepaths, project_root_str)

    # --- PASS 1: Index Definitions & Embeddings ---
    async def process_file_pass1(filepath: str, file_hash: str):
        try:
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks: return 0
            file_git = git_info.get(filepath, {"author": None, "last_modified": None})
            for chunk in chunks:
                chunk.author = file_git.get("author")
                chunk.last_modified = file_git.get("last_modified")
                chunk.content_hash = file_hash
            
            # Embeddings
            texts = [f"{c.language} {c.type} {c.symbol_name}: {c.content}" for c in chunks]
            embeddings = await ollama_client.get_embeddings_batch(texts, semaphore=INFERENCE_SEMAPHORE)
            
            if embeddings:
                vector_store.upsert_chunks(project_root_str, chunks, embeddings)
            
            return len(chunks)
        except Exception as e:
            logger.error(f"Pass 1 (Indexing) failed for {filepath}: {e}")
            return 0

    async def process_file_bounded_pass1(file_data):
        filepath, file_hash = file_data
        async with FILE_PROCESSING_SEMAPHORE:
            return await process_file_pass1(filepath, file_hash)

    # Execute Pass 1
    logger.info("Starting Pass 1: Indexing Definitions...")
    tasks_p1 = [process_file_bounded_pass1(fd) for fd in files_to_process]
    results_p1 = await asyncio.gather(*tasks_p1)
    stats["chunks_indexed"] = sum(results_p1)

    # --- PASS 2: Link Usages ---
    # We must wait for Pass 1 to complete so all definitions are in the DB.
    
    async def process_file_pass2(filepath: str):
        try:
            # We re-parse to get the usages (since we don't store them in DB yet)
            # This is fast as we don't need embeddings/git info/hashing again.
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks: return
            
            # We need the Chunk IDs to be consistent to create edges.
            # parsing generates deterministic IDs based on content/location.
            
            for chunk in chunks:
                linker.link_chunk_usages(project_root_str, chunk)
        except Exception as e:
            logger.error(f"Pass 2 (Linking) failed for {filepath}: {e}")

    async def process_file_bounded_pass2(file_data):
        filepath, _ = file_data
        async with FILE_PROCESSING_SEMAPHORE:
            await process_file_pass2(filepath)

    logger.info("Starting Pass 2: Linking Usages...")
    tasks_p2 = [process_file_bounded_pass2(fd) for fd in files_to_process]
    await asyncio.gather(*tasks_p2)
    
    final_count = vector_store.count_chunks(project_root_str)
from fnmatch import fnmatch

def _should_process_file(filepath: str, project_root: str, include: Optional[str], exclude: Optional[str]) -> bool:
    """
    Determines if a file should be processed based on include/exclude patterns.
    Path matching is done relative to project_root.
    """
    rel_path = os.path.relpath(filepath, project_root).replace(os.path.sep, "/")
    
    # 1. System Ignores (Hard Rules) - checked in os.walk but good to double check
    for ignored in IGNORE_DIRS:
        if ignored in rel_path.split("/"):
            return False
            
    # 2. Exclude Patterns (Highest Priority)
    if exclude and fnmatch(rel_path, exclude):
        return False
        
    # 3. Include Patterns (Selective)
    if include:
        return fnmatch(rel_path, include)
        
    # Default: Process if no include pattern specified
    return True

async def refresh_index_impl(root_path: str = ".", force_full_scan: bool = False, include: str = None, exclude: str = None) -> str:
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path {root} does not exist."
    project_root_str = root.as_posix()

    if force_full_scan:
        vector_store.clear_project(project_root_str)
        knowledge_graph.clear()

    initial_count = vector_store.count_chunks(project_root_str)
    existing_hashes = {} if force_full_scan else vector_store.get_project_hashes(project_root_str)
    
    stats = {"files_scanned": 0, "chunks_indexed": 0, "errors": 0, "initial_count": initial_count, "skipped": 0}
    
    files_to_process = []
    files_to_skip = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.startswith("."): continue
            file_path = Path(dirpath) / f
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                file_str = file_path.resolve().as_posix()
                
                # Check Scope Tuning (Include/Exclude)
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

    # Process only files that changed
    just_filepaths = [f[0] for f in files_to_process]
    git_info = await batch_get_git_info(just_filepaths, project_root_str)

    # --- PASS 1: Index Definitions & Embeddings ---
    async def process_file_pass1(filepath: str, file_hash: str):
        try:
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks: return 0
            file_git = git_info.get(filepath, {"author": None, "last_modified": None})
            for chunk in chunks:
                chunk.author = file_git.get("author")
                chunk.last_modified = file_git.get("last_modified")
                chunk.content_hash = file_hash
            
            # Embeddings
            texts = [f"{c.language} {c.type} {c.symbol_name}: {c.content}" for c in chunks]
            embeddings = await ollama_client.get_embeddings_batch(texts, semaphore=INFERENCE_SEMAPHORE)
            
            if embeddings:
                vector_store.upsert_chunks(project_root_str, chunks, embeddings)
            
            return len(chunks)
        except Exception as e:
            logger.error(f"Pass 1 (Indexing) failed for {filepath}: {e}")
            return 0

    async def process_file_bounded_pass1(file_data):
        filepath, file_hash = file_data
        async with FILE_PROCESSING_SEMAPHORE:
            return await process_file_pass1(filepath, file_hash)

    # Execute Pass 1
    logger.info("Starting Pass 1: Indexing Definitions...")
    tasks_p1 = [process_file_bounded_pass1(fd) for fd in files_to_process]
    results_p1 = await asyncio.gather(*tasks_p1)
    stats["chunks_indexed"] = sum(results_p1)

    # --- PASS 2: Link Usages ---
    # We must wait for Pass 1 to complete so all definitions are in the DB.
    
    async def process_file_pass2(filepath: str):
        try:
            # We re-parse to get the usages (since we don't store them in DB yet)
            # This is fast as we don't need embeddings/git info/hashing again.
            chunks = parser.parse_file(filepath, project_root=project_root_str)
            if not chunks: return
            
            # We need the Chunk IDs to be consistent to create edges.
            # parsing generates deterministic IDs based on content/location.
            
            for chunk in chunks:
                linker.link_chunk_usages(project_root_str, chunk)
        except Exception as e:
            logger.error(f"Pass 2 (Linking) failed for {filepath}: {e}")

    async def process_file_bounded_pass2(file_data):
        filepath, _ = file_data
        async with FILE_PROCESSING_SEMAPHORE:
            await process_file_pass2(filepath)

    logger.info("Starting Pass 2: Linking Usages...")
    tasks_p2 = [process_file_bounded_pass2(fd) for fd in files_to_process]
    await asyncio.gather(*tasks_p2)
    
    final_count = vector_store.count_chunks(project_root_str)
    scan_type = "Full Rebuild" if force_full_scan else "Incremental Update"
    return (
        f"Indexing Complete for project: {project_root_str}\n"
        f"Scan Type: {scan_type}\n"
        f"Files Scanned: {stats['files_scanned']} ({stats['skipped']} skipped)\n"
        f"Total Chunks in Index: {final_count}"
    )

@mcp.tool()
async def refresh_index(root_path: str = ".", force_full_scan: bool = False, include: str = None, exclude: str = None) -> str:
    """
    Scans, parses, and indexes the codebase for semantic search and symbol linking.
    
    BEST FOR:
    - First-time initialization of a project workspace.
    - Synchronizing the index after a major refactor or git pull.
    - Rebuilding the 'Knowledge Graph' (edges) to fix broken jump-to-definition links.
    - Targeting specific directories for re-indexing (via 'include').
    
    Args:
        root_path: The absolute path to the project root. Defaults to current directory.
        force_full_scan: If True, wipes the existing index and performs a total rebuild. 
                         Use this if the index feels stale or corrupted.
        include: Optional glob pattern to ONLY index matching files (e.g., 'src/api/**').
        exclude: Optional glob pattern to SKIP matching files (e.g., 'tests/**').
    """
    return await refresh_index_impl(root_path, force_full_scan, include, exclude)

async def search_code_impl(query: str, root_path: str = ".", limit: int = 10, include: str = None, exclude: str = None) -> str:
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)
        
        # Determine internal fetch limit. If filtering is active, we need to fetch more
        # candidates from the vector store to ensure we still return 'limit' results after filtering.
        fetch_limit = limit * 5 if (include or exclude) else limit
        
        query_vec = await ollama_client.get_embedding(query)
        results = vector_store.search(project_root_str, query_vec, limit=fetch_limit)
        
        if not results: return f"No matching code found in project: {project_root_str}"
        
        filtered_results = []
        for r in results:
            # Check Scope Tuning
            if _should_process_file(r['filename'], project_root_str, include, exclude):
                filtered_results.append(r)
                if len(filtered_results) >= limit:
                    break
        
        if not filtered_results:
             return f"No matches found after applying filters (fetched {len(results)} raw candidates)."

        output = [f"Results for project: {project_root_str}\n"]
        for r in filtered_results:
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
async def search_code(query: str, root_path: str = ".", limit: int = 10, include: str = None, exclude: str = None) -> str:
    """
    Performs a semantic (vector-based) search over the indexed codebase.
    
    BEST FOR:
    - Finding code related to a concept (e.g., 'how is authentication handled?').
    - Locating similar implementations across the codebase.
    - Navigating unfamiliar projects where specific symbol names aren't known.
    
    The results include 'Project Pulse' metadata (Git author, complexity, dependencies).
    
    Args:
        query: Natural language description of what you are looking for.
        root_path: Project root directory to search within.
        limit: Number of results to return (max recommended: 20).
        include: Optional glob pattern to ONLY return matches from specific files (e.g. 'src/**').
        exclude: Optional glob pattern to HIDE matches from specific files (e.g. 'tests/**').
    """
    return await search_code_impl(query, root_path, limit, include, exclude)

@mcp.tool()
async def get_stats(root_path: str = ".") -> str:
    """
    Provides a high-level architectural overview and 'Project Pulse' health report.
    
    BEST FOR:
    - Identifying 'High-Risk Symbols' (very high complexity with low test coverage).
    - Finding 'Dependency Hubs' (central files that might be refactor targets).
    - Checking the 'Project Pulse' (active branch, stale files).
    - Quantifying language distribution and technical debt.
    
    Args:
        root_path: Project root directory to analyze.
    """
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

@mcp.tool()
async def find_definition(filename: str, line: int, symbol_name: Optional[str] = None, root_path: str = ".") -> str:
    """
    Locates the source code definition for a specific symbol.
    
    BEST FOR:
    - 'Jump to Definition' logic when you encounter an unfamiliar function or class call.
    - Understanding the exact implementation details of a specific component.
    - Resolving imports across multiple files.
    
    Args:
        filename: The file where the symbol is being used.
        line: The line number of the usage.
        symbol_name: The exact name of the function, class, or variable to find.
        root_path: Project root for context.
    """
    return await _find_definition(filename, line, symbol_name, root_path)

async def _find_definition(filename: str, line: int, symbol_name: Optional[str] = None, root_path: str = ".") -> str:
    try:
        project_root = str(Path(root_path).resolve())
        if symbol_name:
            targets = vector_store.find_chunks_by_symbol(project_root, symbol_name)
            if not targets:
                return f"No definition found for symbol '{symbol_name}'"
            
            output = []
            for t in targets:
                output.append(f"File: {t['filename']} ({t['start_line']}-{t['end_line']})\nContent:\n```\n{t['content']}\n```")
            return "\n---\n".join(output)
        
        return "Please provide a symbol_name to find its definition."
    except Exception as e:
        return f"Error finding definition: {e}"

@mcp.tool()
async def find_references(symbol_name: str, root_path: str = ".") -> str:
    """
    Finds all locations where a specific symbol is used or called.
    
    BEST FOR:
    - Assessing the impact of a refactor or breaking change.
    - Finding examples of how a utility function is utilized in real scenarios.
    - Understanding the dependency reach of a specific module.
    
    Args:
        symbol_name: The exact name of the symbol to track references for.
        root_path: Project root context.
    """
    return await _find_references(symbol_name, root_path)

async def _find_references(symbol_name: str, root_path: str = ".") -> str:
    try:
        project_root = str(Path(root_path).resolve())
        # 1. Find the chunk(s) defining the symbol
        def_chunks = vector_store.find_chunks_by_symbol(project_root, symbol_name)
        if not def_chunks:
            return f"Symbol '{symbol_name}' not found in definitions."
            
        all_refs = []
        for d in def_chunks:
            edges = knowledge_graph.get_edges(target_id=d["id"], type="call")
            for source_id, _, _, meta in edges:
                source_chunk = vector_store.get_chunk_by_id(project_root, source_id)
                if source_chunk:
                    match_type = meta.get("match_type", "unknown")
                    confidence = "High" if match_type == "explicit_import" else "Low"
                    all_refs.append(f"Referenced in {source_chunk['filename']} at line {meta.get('line', 'unknown')} ({confidence} Confidence: {match_type})\nChunk: {source_chunk.get('symbol_name', 'N/A')}")
        
        if not all_refs:
            return f"No references found for '{symbol_name}' in the knowledge graph."
            
        return "\n---\n".join(all_refs)
    except Exception as e:
        return f"Error finding references: {e}"

if __name__ == "__main__":
    # Apply stdout protection only when running as a server
    builtins.print = safe_print
    mcp.run()
