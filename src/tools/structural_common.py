import json
from pathlib import Path

from ..git_utils import check_git_dirty
from ..utils import normalize_path


def is_test_file(filename: str) -> bool:
    normalized = filename.replace("\\", "/").lower()
    path = Path(normalized)
    if any(part in {"tests", "test"} for part in path.parts):
        return True
    name = path.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
    )


def edge_confidence(match_type: str) -> str:
    if match_type in {"explicit_import", "local_symbol"}:
        return "exact"
    return "high"


def parse_edge_metadata(edge) -> dict:
    try:
        return json.loads(edge.metadata_json or "{}")
    except json.JSONDecodeError:
        return {}


async def build_freshness(project_root: str, ctx, include: str | None = None, exclude: str | None = None) -> tuple[dict, list[str]]:
    normalized_root = normalize_path(project_root)
    warnings: list[str] = []
    refresh_run = ctx.structural_store.get_refresh_run(normalized_root)

    if refresh_run is None:
        return {
            "projectRoot": normalized_root,
            "structuralState": "missing",
            "enrichmentState": "disabled",
            "lastStructuralRefreshAt": None,
            "lastEnrichmentAt": None,
            "scope": {"include": include, "exclude": exclude},
            "warnings": ["No structural refresh has been recorded yet."],
        }, ["No structural refresh has been recorded yet."]

    is_dirty = await check_git_dirty(normalized_root)
    structural_state = "stale" if is_dirty else "current"
    if is_dirty:
        warnings.append("Repository has uncommitted changes since the last structural refresh.")

    return {
        "projectRoot": normalized_root,
        "structuralState": structural_state,
        "enrichmentState": "disabled",
        "lastStructuralRefreshAt": refresh_run.last_refresh_at,
        "lastEnrichmentAt": None,
        "scope": {"include": include, "exclude": exclude},
        "warnings": warnings,
    }, warnings