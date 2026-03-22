"""Structural-only project stats for the rebooted tool surface."""

import logging
from fnmatch import fnmatch
from collections import Counter, defaultdict
from pathlib import Path

from .structural_common import build_freshness, is_concrete_definition_kind, is_test_file
from ..context import AppContext
from ..git_utils import get_active_branch
from ..utils import normalize_path

logger = logging.getLogger("server")

_CODE_HOTSPOT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".cpp", ".c", ".h",
    ".dart", ".html", ".css", ".rules",
}

_NON_CODE_PATH_PARTS = {
    "docs",
    "doc",
    "bench-results",
    "bench_results",
    "reports",
}


def _count_file_lines(filepath: str) -> int:
    try:
        count = 0
        last_byte = b""
        with open(filepath, "rb") as handle:
            while chunk := handle.read(65536):
                count += chunk.count(b"\n")
                last_byte = chunk[-1:]
        if count == 0 and last_byte:
            return 1
        if last_byte and last_byte != b"\n":
            count += 1
        return count
    except OSError:
        return 0


def _direct_test_patterns(filename: str) -> set[str]:
    stem = Path(filename).stem.lower()
    return {
        f"test_{stem}.py",
        f"{stem}_test.py",
        f"{stem}_test.dart",
        f"{stem}.test.ts",
        f"{stem}.test.js",
        f"{stem}.spec.ts",
        f"{stem}.spec.js",
    }


def _is_code_hotspot_file(filename: str) -> bool:
    normalized = filename.replace("\\", "/").lower()
    path = Path(normalized)
    if any(part in _NON_CODE_PATH_PARTS for part in path.parts):
        return False
    return path.suffix in _CODE_HOTSPOT_EXTENSIONS


def _relative_path(filename: str, project_root: str) -> str:
    try:
        normalized_filename = normalize_path(filename)
        normalized_project_root = normalize_path(project_root)
        return Path(normalized_filename).relative_to(Path(normalized_project_root)).as_posix()
    except ValueError:
        return Path(filename).name


def _normalize_roots(roots: list[str] | None) -> list[str]:
    if not roots:
        return []
    normalized: list[str] = []
    for root in roots:
        if not root:
            continue
        cleaned = root.replace("\\", "/").strip("/")
        if cleaned:
            normalized.append(cleaned)
    return sorted(set(normalized))


def _matches_scope(filename: str, project_root: str, include: str | None, exclude: str | None, roots: list[str]) -> bool:
    relative_path = _relative_path(filename, project_root)
    if roots and not any(relative_path == root or relative_path.startswith(f"{root}/") for root in roots):
        return False
    if exclude and fnmatch(relative_path, exclude):
        return False
    if include and not fnmatch(relative_path, include):
        return False
    return True


def _split_tracked_files(
    tracked_files: list[str],
    project_root: str,
    view: str,
    include: str | None,
    exclude: str | None,
    roots: list[str] | None,
) -> tuple[list[str], list[str], list[str]]:
    normalized_roots = _normalize_roots(roots)
    scoped_files = [
        file_path
        for file_path in tracked_files
        if _matches_scope(file_path, project_root, include, exclude, normalized_roots)
    ]

    selected_files: list[str] = []
    non_code_files: list[str] = []
    test_files_excluded: list[str] = []

    for file_path in scoped_files:
        if view == "tests":
            if is_test_file(file_path):
                selected_files.append(file_path)
            continue

        if view == "all":
            selected_files.append(file_path)
            if not is_test_file(file_path) and not _is_code_hotspot_file(file_path):
                non_code_files.append(file_path)
            continue

        if is_test_file(file_path):
            test_files_excluded.append(file_path)
            continue
        if _is_code_hotspot_file(file_path):
            selected_files.append(file_path)
        else:
            non_code_files.append(file_path)

    return selected_files, non_code_files, test_files_excluded


def _top_large_files(tracked_files: list[str], file_loc: dict[str, int], symbol_counts: Counter, import_counts: Counter) -> list[dict]:
    ranked = sorted(
        tracked_files,
        key=lambda file_path: (-file_loc.get(file_path, 0), file_path),
    )
    return [
        {
            "file": file_path,
            "loc": file_loc.get(file_path, 0),
            "symbolCount": int(symbol_counts.get(file_path, 0)),
            "importCount": int(import_counts.get(file_path, 0)),
            "isTest": is_test_file(file_path),
        }
        for file_path in ranked[:10]
    ]


def _non_code_large_files(tracked_files: list[str], file_loc: dict[str, int]) -> list[dict]:
    ranked = sorted(
        tracked_files,
        key=lambda file_path: (-file_loc.get(file_path, 0), file_path),
    )
    return [
        {
            "file": file_path,
            "loc": file_loc.get(file_path, 0),
            "kind": Path(file_path).suffix.lower() or "<none>",
            "reason": "Excluded from default hotspot ranking because it is not a code-like source file.",
        }
        for file_path in ranked[:10]
    ]


def _largest_symbols(symbols: list) -> list[dict]:
    records = []
    for record in symbols:
        if not is_concrete_definition_kind(record.symbol_kind):
            continue
        loc = max(0, int(record.end_line) - int(record.start_line) + 1)
        display_name = record.symbol_name
        if record.parent_symbol:
            display_name = f"{record.parent_symbol}.{record.symbol_name}"
        records.append(
            {
                "symbol": display_name,
                "file": record.filename,
                "kind": record.symbol_kind,
                "loc": loc,
            }
        )
    return sorted(records, key=lambda item: (-item["loc"], item["file"], item["symbol"]))[:10]


def _dependency_hubs(imports: list) -> tuple[list[dict], list[dict], dict[str, int]]:
    fan_out_counter: Counter = Counter()
    fan_in_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    fan_in_by_file: Counter = Counter()

    for record in imports:
        fan_out_counter[record.filename] += 1
        target = record.resolved_path or record.import_text
        scope = "internal" if record.resolved_path else "external"
        fan_in_sources[(target, scope)].add(record.filename)
        if record.resolved_path:
            fan_in_by_file[record.resolved_path] += 1

    fan_out = [
        {"file": file_path, "imports": int(count)}
        for file_path, count in fan_out_counter.most_common(10)
    ]
    fan_in = sorted(
        (
            {"target": target, "imports": len(sources), "scope": scope}
            for (target, scope), sources in fan_in_sources.items()
        ),
        key=lambda item: (-item["imports"], item["target"]),
    )[:10]
    return fan_in, fan_out, {file_path: int(count) for file_path, count in fan_in_by_file.items()}


def _threshold_violations(tracked_files: list[str], file_loc: dict[str, int], symbols: list) -> list[dict]:
    violations: list[dict] = []
    for file_path in tracked_files:
        loc = file_loc.get(file_path, 0)
        if loc > 200:
            violations.append(
                {
                    "rule": "file_loc",
                    "file": file_path,
                    "actual": loc,
                    "threshold": 200,
                    "reason": "File exceeds the 200 line guideline.",
                }
            )

    for record in symbols:
        loc = max(0, int(record.end_line) - int(record.start_line) + 1)
        if record.symbol_name == "build" and loc > 50 and ("method" in record.symbol_kind or "function" in record.symbol_kind):
            violations.append(
                {
                    "rule": "flutter_build_loc",
                    "file": record.filename,
                    "symbol": record.symbol_name,
                    "actual": loc,
                    "threshold": 50,
                    "reason": "Build method exceeds the 50 line guideline.",
                }
            )

    return sorted(violations, key=lambda item: (-int(item["actual"]), item["file"]))[:20]


def _test_gap_candidates(tracked_files: list[str], test_names: set[str], file_loc: dict[str, int], fan_in_by_file: dict[str, int], fan_out_by_file: Counter) -> tuple[list[dict], dict[str, int]]:
    test_gap_flags: dict[str, int] = {}
    candidates: list[dict] = []

    for file_path in tracked_files:
        if is_test_file(file_path):
            continue

        loc = file_loc.get(file_path, 0)
        direct_match = bool(_direct_test_patterns(file_path) & test_names)
        test_gap = int(loc >= 75 and not direct_match)
        test_gap_flags[file_path] = test_gap
        if not test_gap:
            continue

        candidates.append(
            {
                "file": file_path,
                "loc": loc,
                "fanIn": int(fan_in_by_file.get(file_path, 0)),
                "fanOut": int(fan_out_by_file.get(file_path, 0)),
                "reason": "Large production file has no direct test match.",
            }
        )

    return sorted(candidates, key=lambda item: (-item["loc"], -item["fanIn"], item["file"]))[:10], test_gap_flags


def _refactor_candidates(tracked_files: list[str], file_loc: dict[str, int], fan_in_by_file: dict[str, int], fan_out_by_file: Counter, test_gap_flags: dict[str, int]) -> list[dict]:
    source_files = [file_path for file_path in tracked_files if not is_test_file(file_path)]
    if not source_files:
        return []

    max_loc = max((file_loc.get(file_path, 0) for file_path in source_files), default=0) or 1
    max_fan_in = max((fan_in_by_file.get(file_path, 0) for file_path in source_files), default=0) or 1
    max_fan_out = max((int(fan_out_by_file.get(file_path, 0)) for file_path in source_files), default=0) or 1

    candidates = []
    for file_path in source_files:
        loc = file_loc.get(file_path, 0)
        fan_in = int(fan_in_by_file.get(file_path, 0))
        fan_out = int(fan_out_by_file.get(file_path, 0))
        test_gap = int(test_gap_flags.get(file_path, 0))

        score = round(
            (0.45 * (loc / max_loc))
            + (0.30 * (fan_in / max_fan_in))
            + (0.15 * (fan_out / max_fan_out))
            + (0.10 * test_gap),
            3,
        )

        reasons = []
        if loc >= 200:
            reasons.append("high_loc")
        if fan_in > 0 and fan_in == max_fan_in:
            reasons.append("import_hub")
        if fan_out > 0 and fan_out == max_fan_out:
            reasons.append("high_fan_out")
        if test_gap:
            reasons.append("missing_direct_test")
        if not reasons:
            reasons.append("size_and_dependency_weight")

        candidates.append(
            {
                "file": file_path,
                "score": score,
                "metrics": {
                    "loc": loc,
                    "fanIn": fan_in,
                    "fanOut": fan_out,
                    "testGap": test_gap,
                },
                "reasons": reasons,
            }
        )

    return sorted(candidates, key=lambda item: (-item["score"], item["file"]))[:10]


async def get_stats_impl(
    root_path: str = ".",
    ctx: AppContext = None,
    view: str = "code",
    include: str | None = None,
    exclude: str | None = None,
    roots: list[str] | None = None,
) -> dict:
    """Return a structured hotspot report based on structural-core facts."""
    try:
        project_root_str = normalize_path(root_path)
        selected_view = (view or "code").lower()
        if selected_view not in {"code", "tests", "all"}:
            selected_view = "code"
        normalized_roots = _normalize_roots(roots)

        if ctx is None or ctx.structural_store is None:
            freshness = {
                "projectRoot": project_root_str,
                "structuralState": "missing",
                "workspaceState": "unknown",
                "enrichmentState": "disabled",
                "lastStructuralRefreshAt": None,
                "lastEnrichmentAt": None,
                "scope": {"include": include, "exclude": exclude},
                "warnings": ["Structural store is not initialized."],
            }
            return {
                "status": "error",
                "summary": "Structural store is not initialized.",
                "freshness": freshness,
                "overview": {},
                "hotspotScope": {},
                "projectPulse": {},
                "topLargeFiles": [],
                "nonCodeLargeFiles": [],
                "largestSymbols": [],
                "dependencyHubs": {"fanIn": [], "fanOut": []},
                "thresholdViolations": [],
                "testGapCandidates": [],
                "refactorCandidates": [],
                "warnings": ["Structural store is not initialized."],
            }

        stats = ctx.structural_store.get_project_stats(project_root_str)
        freshness, freshness_warnings = await build_freshness(project_root_str, ctx, include=include, exclude=exclude)

        if not stats:
            return {
                "status": "missing",
                "summary": f"No structural index found for project: {project_root_str}",
                "freshness": freshness,
                "overview": {},
                "hotspotScope": {},
                "projectPulse": {},
                "topLargeFiles": [],
                "nonCodeLargeFiles": [],
                "largestSymbols": [],
                "dependencyHubs": {"fanIn": [], "fanOut": []},
                "thresholdViolations": [],
                "testGapCandidates": [],
                "refactorCandidates": [],
                "warnings": sorted(set(freshness_warnings + [f"No structural index found for project: {project_root_str}"])),
            }

        branch = await get_active_branch(project_root_str)
        tracked_files = ctx.structural_store.list_tracked_files(project_root_str)
        selected_files, non_code_files, test_files_excluded = _split_tracked_files(
            tracked_files,
            project_root_str,
            selected_view,
            include,
            exclude,
            normalized_roots,
        )
        selected_file_set = set(selected_files)
        symbols = [
            record for record in ctx.structural_store.list_symbols(project_root_str)
            if record.filename in selected_file_set
        ]
        imports = [
            record for record in ctx.structural_store.list_imports(project_root_str)
            if record.filename in selected_file_set
        ]

        file_loc = {file_path: _count_file_lines(file_path) for file_path in tracked_files}
        symbol_counts = Counter(record.filename for record in symbols if is_concrete_definition_kind(record.symbol_kind))
        import_counts = Counter(record.filename for record in imports)
        test_names = {Path(file_path).name.lower() for file_path in tracked_files if is_test_file(file_path)}

        top_large_files = _top_large_files(selected_files, file_loc, symbol_counts, import_counts)
        non_code_large_files = _non_code_large_files(non_code_files, file_loc) if selected_view != "tests" else []
        largest_symbols = _largest_symbols(symbols)
        fan_in, fan_out, fan_in_by_file = _dependency_hubs(imports)
        threshold_violations = _threshold_violations(selected_files, file_loc, symbols)
        source_candidate_files = [
            file_path for file_path in selected_files
            if not is_test_file(file_path) and _is_code_hotspot_file(file_path)
        ]
        if selected_view == "tests":
            test_gap_candidates = []
            refactor_candidates = []
        else:
            test_gap_candidates, test_gap_flags = _test_gap_candidates(
                source_candidate_files,
                test_names,
                file_loc,
                fan_in_by_file,
                import_counts,
            )
            refactor_candidates = _refactor_candidates(
                source_candidate_files,
                file_loc,
                fan_in_by_file,
                import_counts,
                test_gap_flags,
            )

        refresh_run = stats.get("refresh_run")
        top_candidate = refactor_candidates[0]["file"] if refactor_candidates else None
        scope_phrase = f"{len(selected_files)} files considered in the {selected_view} view"
        if normalized_roots:
            scope_phrase += f", rooted to {normalized_roots}"
        summary = (
            f"{stats['tracked_files']} tracked files, {scope_phrase}. "
            f"Top refactor candidate: {top_candidate}."
            if top_candidate
            else f"{stats['tracked_files']} tracked files, {scope_phrase}."
        )

        warnings = sorted(set(freshness_warnings))
        if selected_view == "code" and test_files_excluded:
            warnings.append(
                "Code view excludes test files; use view='tests' for test hotspots or view='all' for the combined view."
            )
        if non_code_files:
            warnings.append(
                "Hotspot ranking defaults to code-like files; see nonCodeLargeFiles for excluded tracked files."
            )
        warnings = sorted(set(warnings))
        return {
            "status": "ok",
            "summary": summary,
            "freshness": freshness,
            "overview": {
                "trackedFiles": stats["tracked_files"],
                "indexedSymbols": stats["symbol_count"],
                "indexedImports": stats["import_count"],
                "indexedEdges": stats["edge_count"],
                "languages": stats["languages"],
            },
            "hotspotScope": {
                "defaultView": "code",
                "view": selected_view,
                "filesConsidered": len(selected_files),
                "roots": normalized_roots,
                "include": include,
                "exclude": exclude,
                "testFilesExcluded": len(test_files_excluded),
                "nonCodeFilesExcluded": len(non_code_files),
            },
            "projectPulse": {
                "activeBranch": branch,
                "lastRefreshAt": refresh_run.last_refresh_at if refresh_run else None,
                "lastScanType": refresh_run.scan_type if refresh_run else "unknown",
            },
            "topLargeFiles": top_large_files,
            "nonCodeLargeFiles": non_code_large_files,
            "largestSymbols": largest_symbols,
            "dependencyHubs": {
                "fanIn": fan_in,
                "fanOut": fan_out,
            },
            "thresholdViolations": threshold_violations,
            "testGapCandidates": test_gap_candidates,
            "refactorCandidates": refactor_candidates,
            "warnings": warnings,
        }

    except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError) as e:
        logger.exception("get_stats failed")
        project_root_str = normalize_path(root_path)
        freshness = {
            "projectRoot": project_root_str,
            "structuralState": "missing",
            "workspaceState": "unknown",
            "enrichmentState": "disabled",
            "lastStructuralRefreshAt": None,
            "lastEnrichmentAt": None,
            "scope": {"include": include, "exclude": exclude},
            "warnings": [f"get_stats failed: {e}"],
        }
        return {
            "status": "error",
            "summary": f"Failed to get stats: {e}",
            "freshness": freshness,
            "overview": {},
            "hotspotScope": {},
            "projectPulse": {},
            "topLargeFiles": [],
            "nonCodeLargeFiles": [],
            "largestSymbols": [],
            "dependencyHubs": {"fanIn": [], "fanOut": []},
            "thresholdViolations": [],
            "testGapCandidates": [],
            "refactorCandidates": [],
            "warnings": [f"Failed to get stats: {e}"],
        }
