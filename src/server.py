import sys
import logging
import builtins
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
from .tools.inspect import inspect_symbol_impl
from .tools.impact import impact_analysis_impl
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
    )


def _disabled_legacy_tool_message(tool_name: str) -> str:
    return (
        f"{tool_name} is disabled on feature/structural-context-pivot. "
        "This branch is testing a structural-only foundation. "
        "Use refresh_index and get_stats until reboot-native replacements are rebuilt on the new core."
    )


@mcp.tool()
async def search_code(
    query: str,
    root_path: str,
    limit: int = 10,
    include: str = None,
    exclude: str = None,
) -> str:
    return _disabled_legacy_tool_message("search_code")


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
async def inspect_symbol(
    root_path: str,
    symbol_name: str,
    filename: str = None,
    line: int = None,
    include_references: bool = True,
    include_dependents: bool = False,
    max_references: int = 50,
) -> dict:
    norm_root = normalize_path(root_path)
    norm_file = normalize_path(filename) if filename else None
    return await inspect_symbol_impl(
        norm_root,
        symbol_name,
        _get_ctx(),
        filename=norm_file,
        line=line,
        include_references=include_references,
        include_dependents=include_dependents,
        max_references=max_references,
    )


@mcp.tool()
async def impact_analysis(
    root_path: str,
    changed_files: list[str] = None,
    changed_symbols: list[str] = None,
    patch_text: str = None,
    include_tests: bool = True,
    max_results: int = 50,
) -> dict:
    norm_root = normalize_path(root_path)
    return await impact_analysis_impl(
        norm_root,
        _get_ctx(),
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        patch_text=patch_text,
        include_tests=include_tests,
        max_results=max_results,
    )


@mcp.tool()
async def find_definition(
    filename: str,
    line: int,
    symbol_name: Optional[str],
    root_path: str,
) -> str:
    return _disabled_legacy_tool_message("find_definition")


@mcp.tool()
async def find_references(symbol_name: str, root_path: str) -> str:
    return _disabled_legacy_tool_message("find_references")


if __name__ == "__main__":
    # Apply stdout protection only when running as a server process.
    builtins.print = safe_print
    mcp.run()
