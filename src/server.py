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
    root_path: str,
    force_full_scan: bool = False,
    include: str = None,
    exclude: str = None,
) -> str:
    """
    Scans, parses, and indexes the codebase.

    Best for: Initializing the workspace or syncing after major changes/refactors.

    Args:
        root_path: MUST be the absolute path to the active workspace project root (e.g., 'd:/workspace/my-project'). NEVER use '.' or relative paths.
        force_full_scan: True to wipe and rebuild the index.
        include: Glob pattern to ONLY index matching files (e.g., 'src/**').
        exclude: Glob pattern to SKIP matching files (e.g., 'tests/**').
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
    root_path: str,
    limit: int = 10,
    include: str = None,
    exclude: str = None,
) -> str:
    """
    Semantic (vector-based) search over the codebase.

    Best for: Finding code related to a concept or locating similar implementations.

    Args:
        query: Natural language description of what you are looking for.
        root_path: MUST be the absolute path to the active workspace project root. NEVER use '.' or relative paths.
        limit: Max results to return (recommended: 10-20).
        include: Glob filter for files to search within (e.g., 'src/**').
        exclude: Glob filter for files to ignore.
    """
    norm_root = normalize_path(root_path)
    return await search_code_impl(query, _get_ctx(), norm_root, limit, include, exclude)


@mcp.tool()
async def get_stats(root_path: str) -> str:
    """
    Provides a high-level architectural overview and health report.

    Best for: Checking project health, finding high-risk symbols, or identifying dependency hubs.

    Args:
        root_path: MUST be the absolute path to the active workspace project root. NEVER use '.' or relative paths.
    """
    norm_root = normalize_path(root_path)
    return await get_stats_impl(norm_root, _get_ctx())


@mcp.tool()
async def find_definition(
    filename: str,
    line: int,
    symbol_name: Optional[str],
    root_path: str,
) -> str:
    """
    Locates the source code definition for a specific symbol used in a file.

    Best for: 'Jump to Definition' to understand implementation details or resolve imports.

    Args:
        filename: Absolute path to the file where the symbol is used.
        line: The line number where the symbol is referenced (1-indexed).
        symbol_name: The exact name of the function, class, or variable.
        root_path: MUST be the absolute path to the active workspace project root. NEVER use '.' or relative paths.
    """
    norm_root = normalize_path(root_path)
    norm_file = normalize_path(filename)
    return await find_definition_impl(norm_file, line, symbol_name, norm_root, _get_ctx())


@mcp.tool()
async def find_references(symbol_name: str, root_path: str) -> str:
    """
    Finds all locations where a specific symbol is used or called.

    Best for: Assessing refactoring impact or finding usage examples of a shared utility.

    Args:
        symbol_name: The exact name of the symbol to track.
        root_path: MUST be the absolute path to the active workspace project root. NEVER use '.' or relative paths.
    """
    norm_root = normalize_path(root_path)
    return await find_references_impl(symbol_name, norm_root, _get_ctx())


if __name__ == "__main__":
    # Apply stdout protection only when running as a server process.
    builtins.print = safe_print
    mcp.run()
