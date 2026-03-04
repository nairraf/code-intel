import sys
import logging
import asyncio
import builtins
import traceback
from typing import Optional

from fastmcp import FastMCP

# --- STDOUT FORTRESS ---
# Must intercept print before any other import that might write to stdout.
_original_print = builtins.print


def safe_print(*args, **kwargs):
    if 'file' not in kwargs or kwargs['file'] is None or kwargs['file'] == sys.stdout:
        kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)


from .config import LOG_DIR
from .utils import normalize_path
from .context import get_context
from .indexer import refresh_index_impl
from .tools.definition import find_definition_impl
from .tools.references import find_references_impl
from .tools.search import search_code_impl
from .tools.stats import get_stats_impl

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "server.log", encoding='utf-8'),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# MCP instance + shared services
# ---------------------------------------------------------------------------
mcp = FastMCP("Lightweight Code Intel")

# Concurrency guards
INFERENCE_SEMAPHORE = asyncio.Semaphore(5)
FILE_PROCESSING_SEMAPHORE = asyncio.Semaphore(10)


def _get_ctx():
    """Return the shared AppContext, lazily initialised on first call.

    Using a helper rather than a module-level assignment prevents DB connections
    and HTTP clients from being created at import time (which would break tests
    that patch src.context._context before the first tool invocation).
    """
    return get_context()


# ---------------------------------------------------------------------------
# MCP tool registrations (thin wrappers — business logic lives in sub-modules)
# ---------------------------------------------------------------------------

@mcp.tool()
async def refresh_index(
    root_path: str = ".",
    force_full_scan: bool = False,
    include: str = None,
    exclude: str = None,
) -> str:
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
    norm_root = normalize_path(root_path)
    return await refresh_index_impl(
        norm_root, force_full_scan, include, exclude,
        ctx=_get_ctx(),
        inference_semaphore=INFERENCE_SEMAPHORE,
        file_semaphore=FILE_PROCESSING_SEMAPHORE,
    )


@mcp.tool()
async def search_code(
    query: str,
    root_path: str = ".",
    limit: int = 10,
    include: str = None,
    exclude: str = None,
) -> str:
    """
    Performs a semantic (vector-based) search over the indexed codebase.

    BEST FOR:
    - Finding code related to a concept (e.g., 'how is authentication handled?').
    - Locating similar implementations across the codebase.
    - Navigating unfamiliar projects where specific symbol names aren't known.

    The results will include chunk-level author, modification date, and complexity metadata.
    Note: for broader architectural project pulse tracking, utilize the `get_stats` tool.

    Args:
        query: Natural language description of what you are looking for.
        root_path: Project root directory to search within.
        limit: Number of results to return (max recommended: 20).
        include: Optional glob pattern to ONLY return matches from specific files (e.g. 'src/**').
        exclude: Optional glob pattern to HIDE matches from specific files (e.g. 'tests/**').
    """
    norm_root = normalize_path(root_path)
    return await search_code_impl(query, _get_ctx(), norm_root, limit, include, exclude)


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
    norm_root = normalize_path(root_path)
    return await get_stats_impl(norm_root, _get_ctx())


@mcp.tool()
async def find_definition(
    filename: str,
    line: int,
    symbol_name: Optional[str] = None,
    root_path: str = ".",
) -> str:
    """
    Locates the source code definition for a specific symbol.

    BEST FOR:
    - 'Jump to Definition' logic when you encounter an unfamiliar function or class call.
    - Understanding the exact implementation details of a specific component.
    - Resolving imports across multiple files.

    Note: For dynamic dependency injection or highly nested python decorators, fallback
    literal searches via `grep_search` may be required if Knowledge Graph mapping fails.

    Args:
        filename: The file where the symbol is being used.
        line: The line number of the usage (must be exactly on the line where the symbol
              is referenced/called).
        symbol_name: The exact name of the function, class, or variable to find.
        root_path: Project root for context.
    """
    norm_root = normalize_path(root_path)
    norm_file = normalize_path(filename)
    return await find_definition_impl(norm_file, line, symbol_name, norm_root, _get_ctx())


@mcp.tool()
async def find_references(symbol_name: str, root_path: str = ".") -> str:
    """
    Finds all locations where a specific symbol is used or called.

    BEST FOR:
    - Assessing the impact of a refactor or breaking change.
    - Finding examples of how a utility function is utilized in real scenarios.
    - Tracking middleware dependencies (e.g. FastAPI `Depends()`, standard decorators).

    Note: Tracking dynamic middleware injection requires that `refresh_index` with
    `force_full_scan=True` is run on the workspace.

    Args:
        symbol_name: The exact name of the symbol to track references for.
        root_path: Project root context.
    """
    norm_root = normalize_path(root_path)
    return await find_references_impl(symbol_name, norm_root, _get_ctx())


if __name__ == "__main__":
    # Apply stdout protection only when running as a server process.
    builtins.print = safe_print
    mcp.run()
