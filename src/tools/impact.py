import re
from pathlib import Path

from .structural_common import (
    build_freshness,
    edge_confidence,
    is_concrete_definition_kind,
    is_test_file,
    parse_edge_metadata,
    tokenize_identifier_parts,
)
from ..utils import normalize_path


def _normalize_input_files(project_root: str, changed_files: list[str] | None) -> list[str]:
    if not changed_files:
        return []

    normalized_root = normalize_path(project_root)
    normalized_files: list[str] = []
    for file_path in changed_files:
        if not file_path:
            continue
        if Path(file_path).is_absolute():
            normalized_files.append(normalize_path(file_path))
        else:
            normalized_files.append(normalize_path(str(Path(normalized_root) / file_path)))
    return sorted(set(normalized_files))


def _extract_inputs_from_patch(project_root: str, patch_text: str | None) -> tuple[list[str], list[str], list[str]]:
    if not patch_text:
        return [], [], []

    normalized_root = normalize_path(project_root)
    warnings = ["Patch text was parsed heuristically for changed files and symbols."]
    changed_files: list[str] = []
    changed_symbols: list[str] = []

    for match in re.finditer(r"^\+\+\+\s+b/(.+)$", patch_text, flags=re.MULTILINE):
        relative_path = match.group(1).strip()
        if relative_path != "/dev/null":
            changed_files.append(normalize_path(str(Path(normalized_root) / relative_path)))

    symbol_patterns = [
        r"^[+-]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^[+-]\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^[+-]\s*function\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    for pattern in symbol_patterns:
        changed_symbols.extend(re.findall(pattern, patch_text, flags=re.MULTILINE))

    return sorted(set(changed_files)), sorted(set(changed_symbols)), warnings


def _candidate_tests(
    tracked_files: list[str],
    affected_files: list[dict],
    affected_symbols: list[dict],
    max_results: int,
) -> list[dict]:
    tests = [filename for filename in tracked_files if is_test_file(filename)]
    if not tests:
        return []

    ranked: dict[str, tuple[int, dict]] = {}

    for affected_file in affected_files:
        test_file = affected_file["file"]
        if not is_test_file(test_file):
            continue
        ranked[test_file] = (
            100,
            {
                "file": test_file,
                "confidence": affected_file["confidence"],
                "reasons": ["structural dependency on changed symbol"],
                "evidence": list(affected_file["evidence"]),
            },
        )

    if ranked:
        ordered = sorted(ranked.values(), key=lambda item: (-item[0], item[1]["file"]))
        return [payload for _, payload in ordered[:max_results]]

    file_tokens = set()
    for affected_file in affected_files:
        file_tokens.update(tokenize_identifier_parts(Path(affected_file["file"]).stem))

    symbol_tokens = set()
    for affected_symbol in affected_symbols:
        symbol_tokens.update(tokenize_identifier_parts(affected_symbol["symbol"]))

    for test_file in tests:
        if test_file in ranked:
            continue

        test_tokens = tokenize_identifier_parts(test_file)
        reasons: list[str] = []
        score = 0
        for token in file_tokens:
            if token in test_tokens:
                reasons.append("filename heuristic matches affected file")
                score += 2
        for token in symbol_tokens:
            if token in test_tokens:
                reasons.append("filename heuristic matches affected symbol")
                score += 1
        if score == 0:
            continue
        ranked[test_file] = (
            score,
            {
                "file": test_file,
                "confidence": "medium",
                "reasons": sorted(set(reasons)),
                "evidence": [],
            },
        )

    ordered = sorted(ranked.values(), key=lambda item: (-item[0], item[1]["file"]))
    return [payload for _, payload in ordered[:max_results]]


async def impact_analysis_impl(
    root_path: str,
    ctx,
    changed_files: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    patch_text: str | None = None,
    include_tests: bool = True,
    max_results: int = 50,
) -> dict:
    project_root = normalize_path(root_path)
    warnings: list[str] = []
    freshness, freshness_warnings = await build_freshness(project_root, ctx)
    warnings.extend(freshness_warnings)

    normalized_changed_files = _normalize_input_files(project_root, changed_files)
    normalized_changed_symbols = sorted(set(changed_symbols or []))
    patch_files, patch_symbols, patch_warnings = _extract_inputs_from_patch(project_root, patch_text)
    warnings.extend(patch_warnings)
    normalized_changed_files = sorted(set(normalized_changed_files + patch_files))
    normalized_changed_symbols = sorted(set(normalized_changed_symbols + patch_symbols))

    affected_symbols_map: dict[str, dict] = {}
    for filename in normalized_changed_files:
        for record in ctx.structural_store.list_symbols(project_root, filename):
            if not is_concrete_definition_kind(record.symbol_kind):
                continue
            affected_symbols_map[record.symbol_id] = {
                "symbol": record.symbol_name,
                "file": record.filename,
                "confidence": "exact",
                "reasons": ["definition file changed"],
                "evidence": [
                    {
                        "kind": "heuristic",
                        "reason": "Symbol is defined in a changed file.",
                        "source": record.filename,
                        "line": record.start_line,
                        "confidence": "exact",
                    }
                ],
            }

    for symbol_name in normalized_changed_symbols:
        symbol_records = ctx.structural_store.find_symbols(project_root, symbol_name)
        concrete_records = [record for record in symbol_records if is_concrete_definition_kind(record.symbol_kind)]
        for record in concrete_records or symbol_records:
            payload = affected_symbols_map.setdefault(
                record.symbol_id,
                {
                    "symbol": record.symbol_name,
                    "file": record.filename,
                    "confidence": "exact",
                    "reasons": [],
                    "evidence": [],
                },
            )
            payload["reasons"].append("symbol explicitly marked changed")
            payload["evidence"].append(
                {
                    "kind": "heuristic",
                    "reason": f"Input explicitly named symbol '{symbol_name}' as changed.",
                    "source": record.filename,
                    "line": record.start_line,
                    "confidence": "exact",
                }
            )

    affected_files_map: dict[str, dict] = {}
    for filename in normalized_changed_files:
        affected_files_map[filename] = {
            "file": filename,
            "confidence": "exact",
            "reasons": ["file changed"],
            "evidence": [],
        }

    changed_file_set = set(normalized_changed_files)
    incoming_edges = ctx.structural_store.list_incoming_edges(
        project_root,
        list(affected_symbols_map.keys()),
        edge_kind="call",
    )
    seen_file_evidence: set[tuple[str, int, str, str]] = set()
    for edge in incoming_edges:
        metadata = parse_edge_metadata(edge)
        target_symbol = ctx.structural_store.get_symbol_by_id(project_root, edge.target_symbol_id)
        line_number = int(metadata.get("line", 0) or 0)
        match_type = metadata.get("match_type", "exact")
        if match_type == "local_symbol" and edge.source_filename == edge.target_filename:
            continue

        evidence_key = (edge.source_filename, line_number, edge.target_symbol_id, match_type)
        if evidence_key in seen_file_evidence:
            continue
        seen_file_evidence.add(evidence_key)

        confidence = edge_confidence(match_type)
        reason = "calls changed symbol"
        if target_symbol is not None:
            reason = f"calls changed symbol {target_symbol.symbol_name}"
        payload = affected_files_map.setdefault(
            edge.source_filename,
            {
                "file": edge.source_filename,
                "confidence": confidence,
                "reasons": [],
                "evidence": [],
            },
        )
        if edge.source_filename not in changed_file_set or reason not in payload["reasons"]:
            payload["reasons"].append(reason)
        payload["evidence"].append(
            {
                "kind": metadata.get("context", edge.edge_kind),
                "reason": f"Exact structural edge via {match_type}.",
                "source": edge.source_filename,
                "line": line_number,
                "confidence": confidence,
            }
        )

    affected_symbols = list(affected_symbols_map.values())
    for payload in affected_symbols:
        payload["reasons"] = sorted(set(payload["reasons"]))
    affected_symbols.sort(key=lambda item: (item["file"], item["symbol"]))

    affected_files = list(affected_files_map.values())
    for payload in affected_files:
        payload["reasons"] = sorted(set(payload["reasons"]))
    affected_files.sort(key=lambda item: (item["file"]))
    affected_files = affected_files[:max_results]
    affected_symbols = affected_symbols[:max_results]

    tracked_files = ctx.structural_store.list_tracked_files(project_root)
    candidate_tests = (
        _candidate_tests(
            tracked_files,
            affected_files,
            affected_symbols,
            max_results,
        )
        if include_tests
        else []
    )

    if not normalized_changed_files and not normalized_changed_symbols and not patch_text:
        warnings.append("No changed_files, changed_symbols, or patch_text were provided.")

    summary = (
        f"Impact analysis identified {len(affected_files)} affected files, "
        f"{len(affected_symbols)} affected symbols, and {len(candidate_tests)} candidate tests."
    )

    return {
        "status": "ok",
        "freshness": freshness,
        "summary": summary,
        "affectedFiles": affected_files,
        "affectedSymbols": affected_symbols,
        "candidateTests": candidate_tests,
        "warnings": warnings,
    }