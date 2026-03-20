"""Structural-only project stats for the rebooted tool surface."""

import logging

from ..context import AppContext
from ..git_utils import get_active_branch, check_git_dirty

from ..utils import normalize_path

logger = logging.getLogger("server")


async def get_stats_impl(root_path: str = ".", ctx: AppContext = None) -> str:
    """Return a high-level health report based on structural-core facts."""
    try:
        project_root_str = normalize_path(root_path)

        if ctx is None or ctx.structural_store is None:
            return "Error: Structural store not initialized."

        stats = ctx.structural_store.get_project_stats(project_root_str)

        if not stats:
            return f"No structural index found for project: {project_root_str}"

        lang_breakdown = "\n".join(
            f"  - {lang}: {count} symbols" for lang, count in stats["languages"].items()
        )
        if not lang_breakdown:
            lang_breakdown = "  - None"

        summary = (
            f"Stats for: {project_root_str}\n"
            f"Tracked Files:    {stats['tracked_files']}\n"
            f"Indexed Symbols:  {stats['symbol_count']}\n"
            f"Indexed Imports:  {stats['import_count']}\n"
            f"Indexed Edges:    {stats['edge_count']}\n"
            f"Languages:\n{lang_breakdown}"
        )

        hubs = "\n".join(
            f"  - {h['import_text']} ({h['count']} imports)"
            for h in stats.get("dependency_hubs", [])[:5]
        )
        if not hubs:
            hubs = "  - None"

        branch = await get_active_branch(project_root_str)
        refresh_run = stats.get("refresh_run")
        if refresh_run is None:
            structural_state = "MISSING"
            state_reason = "No structural refresh has been recorded yet."
            pulse = (
                f"\n\nProject Pulse:\n"
                f"  - Active Branch:   {branch}\n"
                f"  - Structural State: {structural_state} ({state_reason})"
            )
        else:
            is_dirty = await check_git_dirty(project_root_str)
            structural_state = "DIRTY" if is_dirty else "READY"
            state_reason = (
                "Repository has uncommitted changes since the last structural refresh."
                if is_dirty
                else "Structural facts are available for the current workspace snapshot."
            )
            pulse = (
                f"\n\nProject Pulse:\n"
                f"  - Active Branch:   {branch}\n"
                f"  - Structural State: {structural_state} ({state_reason})\n"
                f"  - Last Refresh:    {refresh_run.last_refresh_at}\n"
                f"  - Last Scan Type:  {refresh_run.scan_type}\n"
                f"  - Files Changed:   {refresh_run.files_changed}\n"
                f"  - Files Skipped:   {refresh_run.files_skipped}"
            )

        return f"{summary}\n\nDependency Hubs:\n{hubs}{pulse}"

    except Exception as e:
        logger.exception("get_stats failed")
        return f"Failed to get stats: {e}"
