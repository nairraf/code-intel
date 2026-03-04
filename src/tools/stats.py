"""
tools/stats.py — get_stats tool implementation.

Provides:
    get_stats_impl: Architectural overview and 'Project Pulse' health report.
"""

import logging
import traceback
from pathlib import Path

from ..context import AppContext
from ..git_utils import get_active_branch

logger = logging.getLogger("server")


async def get_stats_impl(root_path: str = ".", ctx: AppContext = None) -> str:
    """Return a high-level health report for the indexed project.

    Includes language breakdown, complexity metrics, dependency hubs,
    test-coverage gaps, and project pulse (branch + stale files).
    """
    try:
        root = Path(root_path).resolve()
        project_root_str = str(root)

        if ctx is None or ctx.vector_store is None:
            return "Error: Vector store not initialized."

        # Synchronous retrieval — avoids threading issues with LanceDB
        stats = ctx.vector_store.get_detailed_stats(project_root_str)

        if not stats:
            return f"No index found for project: {project_root_str}"

        lang_breakdown = "\n".join(
            f"  - {lang}: {count} chunks" for lang, count in stats["languages"].items()
        )
        summary = (
            f"Stats for: {project_root_str}\n"
            f"Total Chunks:     {stats['chunk_count']}\n"
            f"Unique Files:     {stats['file_count']}\n"
            f"Avg Complexity:   {stats['avg_complexity']:.2f}\n"
            f"Max Complexity:   {stats['max_complexity']}\n"
            f"Languages:\n{lang_breakdown}"
        )

        hubs = "\n".join(
            f"  - {h['file']} ({h['count']} imports)"
            for h in stats.get("dependency_hubs", [])[:5]
        )
        test_gaps = "\n".join(
            f"  - {g['symbol']} ({g['complexity']}) in {Path(g['file']).name}"
            for g in stats.get("test_gaps", [])[:5]
        )

        branch = await get_active_branch(project_root_str)
        pulse = (
            f"\n\nProject Pulse:\n"
            f"  - Active Branch: {branch}\n"
            f"  - Stale Files:   {stats.get('stale_files_count', 0)}"
        )

        return f"{summary}\n\nDependency Hubs:\n{hubs}\n\nTest Gaps:\n{test_gaps}{pulse}"

    except Exception as e:
        logger.error(f"get_stats failed: {e}\n{traceback.format_exc()}")
        return f"Failed to get stats: {e}"
