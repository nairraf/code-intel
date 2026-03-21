"""Structural index trust and freshness inspection for the rebooted tool surface."""

import logging

from .structural_common import build_freshness
from ..context import AppContext
from ..utils import normalize_path

logger = logging.getLogger("server")


def _build_capabilities(stats: dict | None) -> dict:
    if not stats:
        return {
            "structuralNavigation": False,
            "impactAnalysis": False,
            "semanticSearch": False,
            "richFrameworkAnalysis": False,
        }

    symbol_count = int(stats.get("symbol_count", 0) or 0)
    edge_count = int(stats.get("edge_count", 0) or 0)

    return {
        "structuralNavigation": symbol_count > 0,
        "impactAnalysis": symbol_count > 0 and edge_count > 0,
        "semanticSearch": False,
        "richFrameworkAnalysis": False,
    }


async def get_index_status_impl(root_path: str = ".", ctx: AppContext = None) -> dict:
    project_root_str = normalize_path(root_path)
    capabilities = _build_capabilities(None)

    try:
        if ctx is None or ctx.structural_store is None:
            freshness = {
                "projectRoot": project_root_str,
                "structuralState": "missing",
                "workspaceState": "unknown",
                "enrichmentState": "disabled",
                "lastStructuralRefreshAt": None,
                "lastEnrichmentAt": None,
                "scope": {"include": None, "exclude": None},
                "warnings": ["Structural store is not initialized."],
            }
            return {
                "status": "error",
                "freshness": freshness,
                "capabilities": capabilities,
                "warnings": ["Structural store is not initialized."],
            }

        stats = ctx.structural_store.get_project_stats(project_root_str)
        freshness, freshness_warnings = await build_freshness(project_root_str, ctx)
        warnings = list(freshness_warnings)
        capabilities = _build_capabilities(stats)

        if stats is None:
            warnings.append("Run refresh_index before relying on structural tools.")
            warnings.append("Semantic search is disabled on the structural-only reboot branch.")
            warnings.append("Rich framework analysis is not available on the structural-only runtime.")
            return {
                "status": "missing",
                "freshness": freshness,
                "capabilities": capabilities,
                "warnings": warnings,
            }

        if not capabilities["impactAnalysis"]:
            warnings.append("Impact analysis is limited until exact structural edges are available.")
        warnings.append("Semantic search is disabled on the structural-only reboot branch.")
        warnings.append("Rich framework analysis is not available on the structural-only runtime.")

        status = "ok"
        return {
            "status": status,
            "freshness": freshness,
            "capabilities": capabilities,
            "warnings": sorted(set(warnings)),
        }
    except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError) as e:
        logger.exception("get_index_status failed")
        freshness = {
            "projectRoot": project_root_str,
            "structuralState": "missing",
            "workspaceState": "unknown",
            "enrichmentState": "disabled",
            "lastStructuralRefreshAt": None,
            "lastEnrichmentAt": None,
            "scope": {"include": None, "exclude": None},
            "warnings": [f"get_index_status failed: {e}"],
        }
        return {
            "status": "error",
            "freshness": freshness,
            "capabilities": capabilities,
            "warnings": [f"get_index_status failed: {e}"],
        }