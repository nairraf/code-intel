"""
tools/stats.py — get_stats tool implementation.

Provides:
    get_stats_impl: Architectural overview and 'Project Pulse' health report.
"""

import logging
import traceback
from pathlib import Path

from ..context import AppContext
from ..git_utils import get_active_branch, get_current_git_commit, check_git_dirty

from ..utils import normalize_path

logger = logging.getLogger("server")


async def get_stats_impl(root_path: str = ".", ctx: AppContext = None) -> str:
    """Return a high-level health report for the indexed project.
    """
    try:
        project_root_str = normalize_path(root_path)

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

        rule_violations = "\n".join(
            f"  - {v['file']} ({v['rule']})"
            for v in stats.get("rule_violations", [])
        )
        if not rule_violations:
            rule_violations = "  - None"

        branch = await get_active_branch(project_root_str)
        
        # Check freshness
        meta = ctx.vector_store.get_index_metadata(project_root_str)
        freshness_status = "UNKNOWN"
        freshness_reason = "No index metadata found."
        
        if meta:
            current_commit = await get_current_git_commit(project_root_str)
            is_dirty = await check_git_dirty(project_root_str)
            
            idx_commit = meta.get("commit_hash")
            if not current_commit:
                freshness_status = "UNKNOWN"
                freshness_reason = "Not a git repository or git not available."
            elif current_commit != idx_commit:
                freshness_status = "STALE"
                freshness_reason = f"Current commit ({current_commit[:7] if current_commit else 'None'}) differs from indexed commit ({idx_commit[:7] if idx_commit else 'None'})."
            elif is_dirty:
                freshness_status = "DIRTY"
                freshness_reason = "Repository has uncommitted changes since last index."
            else:
                freshness_status = "FRESH"
                freshness_reason = "Index matches current HEAD."

            pulse = (
                f"\n\nProject Pulse:\n"
                f"  - Active Branch:   {branch}\n"
                f"  - Stale Files:     {stats.get('stale_files_count', 0)}\n"
                f"  - Last Indexed:    {meta.get('indexed_at', 'Unknown')}\n"
                f"  - Freshness:       {freshness_status} ({freshness_reason})"
            )
        else:
            pulse = (
                f"\n\nProject Pulse:\n"
                f"  - Active Branch: {branch}\n"
                f"  - Stale Files:   {stats.get('stale_files_count', 0)}\n"
            )

        return f"{summary}\n\nDependency Hubs:\n{hubs}\n\nTest Gaps:\n{test_gaps}\n\nRule Violations:\n{rule_violations}{pulse}"

    except Exception as e:
        logger.error(f"get_stats failed: {e}\n{traceback.format_exc()}")
        return f"Failed to get stats: {e}"
