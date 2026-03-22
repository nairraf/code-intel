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


_TEST_NAME_TOKENS = {"test", "tests", "spec"}
_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".dart": "dart",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}
_SOURCE_ROOT_MARKERS = {"lib", "src", "app", "backend", "api"}
_TEST_ROOT_MARKERS = {"test", "tests"}
_PYTHON_BRIDGE_PREFIXES = ("get_", "create_", "build_", "make_", "provide_")
_PYTHON_BRIDGE_SUFFIXES = ("_provider", "_factory")


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
    ctx,
    project_root: str,
    tracked_files: list[str],
    affected_files: list[dict],
    affected_symbols: list[dict],
    max_results: int,
) -> list[dict]:
    tests = [filename for filename in tracked_files if is_test_file(filename)]
    if not tests:
        return []

    affected_source_files = sorted(
        {
            payload["file"]
            for payload in affected_files
            if not is_test_file(payload["file"])
        }
        | {
            payload["file"]
            for payload in affected_symbols
            if not is_test_file(payload["file"])
        }
    )
    affected_symbol_names = {payload["symbol"] for payload in affected_symbols}
    source_languages = {
        language
        for language in (_file_language(file_path) for file_path in affected_source_files)
        if language is not None
    }
    if source_languages:
        tests = [filename for filename in tests if _file_language(filename) in source_languages]
    if not tests:
        return []

    ranked: dict[str, tuple[int, dict]] = {}

    for affected_file in affected_files:
        test_file = affected_file["file"]
        if not is_test_file(test_file):
            continue
        if source_languages and _file_language(test_file) not in source_languages:
            continue
        ranked[test_file] = (
            1000,
            {
                "file": test_file,
                "confidence": affected_file["confidence"],
                "reasons": ["structural dependency on changed symbol"],
                "evidence": list(affected_file["evidence"]),
            },
        )

    imports_by_test: dict[str, list] = {
        test_file: ctx.structural_store.list_imports(project_root, test_file)
        for test_file in tests
    }
    feature_tokens_by_source = {
        file_path: _feature_tokens(file_path)
        for file_path in affected_source_files
    }

    structural_found = bool(ranked)
    for test_file in tests:
        if test_file in ranked:
            continue

        imports = imports_by_test[test_file]
        resolved_targets = {record.resolved_path for record in imports if record.resolved_path}
        imported_symbols = {
            record.import_text.split("::", 1)[1]
            for record in imports
            if "::" in record.import_text
        }

        reasons: list[str] = []
        evidence: list[dict] = []
        score = 0

        matching_files = sorted(target for target in resolved_targets if target in affected_source_files)
        if matching_files:
            structural_found = True
            score = max(score, 800)
            reasons.append("explicit import of affected file")
            evidence.extend(
                {
                    "kind": "import",
                    "reason": "Test imports an affected file directly.",
                    "source": test_file,
                    "line": 0,
                    "confidence": "high",
                }
                for _ in matching_files[:1]
            )

        matching_symbols = sorted(symbol for symbol in imported_symbols if symbol in affected_symbol_names)
        if matching_symbols:
            structural_found = True
            score = max(score, 780)
            reasons.append("explicit import of affected symbol")
            evidence.extend(
                {
                    "kind": "import",
                    "reason": f"Test imports affected symbol {symbol_name} directly.",
                    "source": test_file,
                    "line": 0,
                    "confidence": "high",
                }
                for symbol_name in matching_symbols[:1]
            )

        if score > 0:
            ranked[test_file] = (
                score,
                {
                    "file": test_file,
                    "confidence": "high",
                    "reasons": sorted(set(reasons)),
                    "evidence": evidence,
                },
            )

    if structural_found:
        ordered = sorted(ranked.values(), key=lambda item: (-item[0], item[1]["file"]))
        return [payload for _, payload in ordered[:max_results]]

    proximity_ranked: dict[str, tuple[int, dict]] = {}
    for test_file in tests:
        test_tokens = _feature_tokens(test_file)
        best_overlap = 0
        for source_tokens in feature_tokens_by_source.values():
            best_overlap = max(best_overlap, len(test_tokens & source_tokens))
        if best_overlap == 0:
            continue

        score = 300 + (best_overlap * 10)
        proximity_ranked[test_file] = (
            score,
            {
                "file": test_file,
                "confidence": "medium",
                "reasons": ["same-feature folder proximity"],
                "evidence": [],
            },
        )

    if proximity_ranked:
        ordered = sorted(proximity_ranked.values(), key=lambda item: (-item[0], item[1]["file"]))
        return [payload for _, payload in ordered[:max_results]]

    file_tokens = set()
    for affected_file in affected_files:
        file_tokens.update(tokenize_identifier_parts(Path(affected_file["file"]).stem))

    symbol_tokens = set()
    for affected_symbol in affected_symbols:
        symbol_tokens.update(tokenize_identifier_parts(affected_symbol["symbol"]))

    for test_file in tests:
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


def _file_language(filename: str) -> str | None:
    return _LANGUAGE_BY_SUFFIX.get(Path(filename).suffix.lower())


def _feature_tokens(filename: str) -> set[str]:
    normalized = filename.replace("\\", "/").lower()
    path = Path(normalized)
    parts = list(path.parts)
    start_index = 0
    for index, part in enumerate(parts[:-1]):
        if part in _SOURCE_ROOT_MARKERS or part in _TEST_ROOT_MARKERS:
            start_index = index + 1
            break

    tokens: set[str] = set()
    for part in parts[start_index:-1]:
        tokens.update(tokenize_identifier_parts(part))

    stem = path.stem
    if stem.startswith("test_"):
        stem = stem[5:]
    if stem.endswith("_test"):
        stem = stem[:-5]
    if stem.endswith("_spec"):
        stem = stem[:-5]
    tokens.update(tokenize_identifier_parts(stem))
    return {token for token in tokens if token not in _TEST_NAME_TOKENS}


def _should_bridge_same_file_local_symbol(source_symbol, context: str) -> bool:
    if source_symbol is None:
        return False
    if source_symbol.language != "python":
        return False
    if is_test_file(source_symbol.filename):
        return False

    symbol_kind = source_symbol.symbol_kind or ""
    normalized_name = source_symbol.symbol_name.lower().lstrip("_")
    if context == "dependency_injection" and ("function" in symbol_kind or "method" in symbol_kind):
        return True
    if "function" in symbol_kind or "method" in symbol_kind:
        return normalized_name.startswith(_PYTHON_BRIDGE_PREFIXES) or normalized_name.endswith(_PYTHON_BRIDGE_SUFFIXES)
    return False


def _find_changed_symbol_records(ctx, project_root: str, symbol_name: str):
    symbol_records = ctx.structural_store.find_symbols(project_root, symbol_name)
    if symbol_records or "." not in symbol_name:
        return symbol_records
    return ctx.structural_store.find_qualified_symbols(project_root, symbol_name)


def _shared_path_prefix_length(left: str, right: str) -> int:
    left_parts = Path(left.replace("\\", "/")).parts[:-1]
    right_parts = Path(right.replace("\\", "/")).parts[:-1]
    shared = 0
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part != right_part:
            break
        shared += 1
    return shared


def _boost_sort_score(payload: dict, score: int) -> None:
    payload["_sort_score"] = max(int(payload.get("_sort_score", 0)), score)


def _incoming_file_score(depth: int) -> int:
    return max(120, 360 - (depth * 60))


def _incoming_symbol_score(depth: int) -> int:
    return max(120, 320 - (depth * 50))


def _collect_component_seed_symbol_ids(ctx, project_root: str, symbol_records) -> set[str]:
    seed_symbol_ids: set[str] = set()
    inspected_files: set[str] = set()

    for record in symbol_records:
        if record.filename in inspected_files or not is_concrete_definition_kind(record.symbol_kind):
            continue
        inspected_files.add(record.filename)
        file_symbols = [
            file_record
            for file_record in ctx.structural_store.list_symbols(project_root, record.filename)
            if is_concrete_definition_kind(file_record.symbol_kind)
        ]
        public_top_level = [
            file_record
            for file_record in file_symbols
            if not file_record.parent_symbol and not file_record.symbol_name.startswith("_")
        ]
        if len(public_top_level) != 1:
            continue

        component_symbol = public_top_level[0]
        if record.symbol_id != component_symbol.symbol_id and record.parent_symbol != component_symbol.symbol_name:
            continue

        seed_symbol_ids.update(file_record.symbol_id for file_record in file_symbols)

    return seed_symbol_ids


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
            if record.parent_symbol:
                continue
            affected_symbols_map[record.symbol_id] = {
                "symbol": record.symbol_name,
                "file": record.filename,
                "confidence": "exact",
                "reasons": ["definition file changed"],
                "_sort_score": 500,
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

    component_seed_symbol_ids: set[str] = set()
    for symbol_name in normalized_changed_symbols:
        symbol_records = _find_changed_symbol_records(ctx, project_root, symbol_name)
        component_seed_symbol_ids.update(_collect_component_seed_symbol_ids(ctx, project_root, symbol_records))
        concrete_records = [record for record in symbol_records if is_concrete_definition_kind(record.symbol_kind)]
        for record in concrete_records or symbol_records:
            payload = affected_symbols_map.setdefault(
                record.symbol_id,
                {
                    "symbol": record.symbol_name,
                    "file": record.filename,
                    "confidence": "exact",
                    "reasons": [],
                    "_sort_score": 400,
                    "evidence": [],
                },
            )
            _boost_sort_score(payload, 400)
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
            "_sort_score": 500,
            "evidence": [],
        }

    changed_file_set = set(normalized_changed_files)
    seen_file_evidence: set[tuple[str, int, str, str]] = set()
    source_symbol_cache: dict[str, object | None] = {}
    bridge_symbol_depths: dict[str, int] = {}

    def get_cached_symbol(symbol_id: str):
        cached_symbol = source_symbol_cache.get(symbol_id)
        if symbol_id not in source_symbol_cache:
            cached_symbol = ctx.structural_store.get_symbol_by_id(project_root, symbol_id)
            source_symbol_cache[symbol_id] = cached_symbol
        return cached_symbol

    def record_bridge_symbol(source_symbol_id: str, target_symbol, line_number: int, confidence: str, depth: int) -> None:
        source_symbol = get_cached_symbol(source_symbol_id)
        if source_symbol is None:
            return
        if not is_concrete_definition_kind(source_symbol.symbol_kind):
            return
        if is_test_file(source_symbol.filename):
            return

        previous_depth = bridge_symbol_depths.get(source_symbol.symbol_id)
        if previous_depth is None or depth < previous_depth:
            bridge_symbol_depths[source_symbol.symbol_id] = depth

        if source_symbol.parent_symbol:
            return
        if source_symbol.symbol_kind == "static_final_declaration_list":
            sibling_symbols = [
                sibling
                for sibling in ctx.structural_store.list_symbols(project_root, source_symbol.filename)
                if sibling.symbol_id != source_symbol.symbol_id
                and not sibling.parent_symbol
                and sibling.symbol_kind == source_symbol.symbol_kind
                and not sibling.symbol_name.startswith("_")
            ]
            for sibling in sibling_symbols:
                sibling_depth = bridge_symbol_depths.get(sibling.symbol_id)
                if sibling_depth is None or depth < sibling_depth:
                    bridge_symbol_depths[sibling.symbol_id] = depth
        if "function" in source_symbol.symbol_kind or "method" in source_symbol.symbol_kind:
            return

        payload = affected_symbols_map.setdefault(
            source_symbol.symbol_id,
            {
                "symbol": source_symbol.symbol_name,
                "file": source_symbol.filename,
                "confidence": confidence,
                "reasons": [],
                "_sort_score": 0,
                "evidence": [],
            },
        )
        _boost_sort_score(payload, _incoming_symbol_score(depth))
        payload["reasons"].append(f"depends on impacted symbol {target_symbol.symbol_name}")
        payload["evidence"].append(
            {
                "kind": "heuristic",
                "reason": f"Exact structural caller of impacted symbol {target_symbol.symbol_name}.",
                "source": source_symbol.filename,
                "line": line_number,
                "confidence": confidence,
            }
        )

    def record_incoming_edge(edge, depth: int) -> None:
        metadata = parse_edge_metadata(edge)
        target_symbol = ctx.structural_store.get_symbol_by_id(project_root, edge.target_symbol_id)
        if target_symbol is None:
            return

        line_number = int(metadata.get("line", 0) or 0)
        match_type = metadata.get("match_type", "exact")
        confidence = edge_confidence(match_type)
        if match_type == "local_symbol" and edge.source_filename == edge.target_filename:
            source_symbol = get_cached_symbol(edge.source_symbol_id)
            if _should_bridge_same_file_local_symbol(source_symbol, metadata.get("context", edge.edge_kind)):
                record_bridge_symbol(edge.source_symbol_id, target_symbol, line_number, confidence, depth)
            return

        evidence_key = (edge.source_filename, line_number, edge.target_symbol_id, match_type)
        if evidence_key in seen_file_evidence:
            return
        seen_file_evidence.add(evidence_key)

        reason_prefix = "calls changed symbol" if depth == 1 else "calls impacted symbol"
        reason = f"{reason_prefix} {target_symbol.symbol_name}"
        payload = affected_files_map.setdefault(
            edge.source_filename,
            {
                "file": edge.source_filename,
                "confidence": confidence,
                "reasons": [],
                "_sort_score": 0,
                "evidence": [],
            },
        )
        _boost_sort_score(payload, _incoming_file_score(depth))
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

        record_bridge_symbol(edge.source_symbol_id, target_symbol, line_number, confidence, depth)

    incoming_edges = ctx.structural_store.list_incoming_edges(
        project_root,
        list(affected_symbols_map.keys()),
        edge_kind="call",
    )
    for edge in incoming_edges:
        record_incoming_edge(edge, depth=1)

    max_incoming_depth = 3
    expanded_bridge_symbols: set[str] = set()
    current_depth = 1
    while current_depth < max_incoming_depth:
        frontier_ids = [
            symbol_id
            for symbol_id, symbol_depth in bridge_symbol_depths.items()
            if symbol_depth == current_depth and symbol_id not in expanded_bridge_symbols
        ]
        if not frontier_ids:
            current_depth += 1
            continue

        expanded_bridge_symbols.update(frontier_ids)
        propagated_edges = ctx.structural_store.list_incoming_edges(
            project_root,
            frontier_ids,
            edge_kind="call",
        )
        for edge in propagated_edges:
            record_incoming_edge(edge, depth=current_depth + 1)
        current_depth += 1

    outgoing_edges = ctx.structural_store.list_outgoing_edges(
        project_root,
        list(component_seed_symbol_ids),
        edge_kind="call",
    )
    collaborator_evidence: set[tuple[str, int, str, str]] = set()
    source_symbol_cache: dict[str, object] = {}
    changed_component_files: set[str] = set()
    for symbol_id in component_seed_symbol_ids:
        source_record = source_symbol_cache.get(symbol_id)
        if source_record is None:
            source_record = ctx.structural_store.get_symbol_by_id(project_root, symbol_id)
            source_symbol_cache[symbol_id] = source_record
        if source_record is not None:
            changed_component_files.add(source_record.filename)

    for edge in outgoing_edges:
        metadata = parse_edge_metadata(edge)
        match_type = metadata.get("match_type", "exact")
        if edge.target_filename in changed_file_set:
            continue
        if match_type == "local_symbol" and edge.source_filename == edge.target_filename:
            continue

        target_symbol = ctx.structural_store.get_symbol_by_id(project_root, edge.target_symbol_id)
        if target_symbol is None or not is_concrete_definition_kind(target_symbol.symbol_kind):
            continue

        line_number = int(metadata.get("line", 0) or 0)
        evidence_key = (edge.target_filename, line_number, edge.target_symbol_id, match_type)
        if evidence_key in collaborator_evidence:
            continue
        collaborator_evidence.add(evidence_key)

        confidence = edge_confidence(match_type)
        source_distance = max(
            (_shared_path_prefix_length(source_file, edge.target_filename) for source_file in changed_component_files),
            default=0,
        )
        collaborator_score = 200 + min(source_distance, 25)

        symbol_payload = affected_symbols_map.setdefault(
            target_symbol.symbol_id,
            {
                "symbol": target_symbol.symbol_name,
                "file": target_symbol.filename,
                "confidence": confidence,
                "reasons": [],
                "_sort_score": 0,
                "evidence": [],
            },
        )
        _boost_sort_score(symbol_payload, collaborator_score)
        symbol_payload["reasons"].append("used directly by changed component")
        symbol_payload["evidence"].append(
            {
                "kind": metadata.get("context", edge.edge_kind),
                "reason": "Direct structural collaborator of the changed component.",
                "source": edge.source_filename,
                "line": line_number,
                "confidence": confidence,
            }
        )

        file_payload = affected_files_map.setdefault(
            edge.target_filename,
            {
                "file": edge.target_filename,
                "confidence": confidence,
                "reasons": [],
                "_sort_score": 0,
                "evidence": [],
            },
        )
        _boost_sort_score(file_payload, collaborator_score)
        file_payload["reasons"].append(
            f"used directly by changed component {target_symbol.symbol_name}"
        )
        file_payload["evidence"].append(
            {
                "kind": metadata.get("context", edge.edge_kind),
                "reason": "Direct structural collaborator of the changed component.",
                "source": edge.source_filename,
                "line": line_number,
                "confidence": confidence,
            }
        )

    affected_symbols = list(affected_symbols_map.values())
    for payload in affected_symbols:
        payload["reasons"] = sorted(set(payload["reasons"]))
    affected_symbols.sort(key=lambda item: (-int(item.get("_sort_score", 0)), item["file"], item["symbol"]))
    for payload in affected_symbols:
        payload.pop("_sort_score", None)

    affected_files = list(affected_files_map.values())
    for payload in affected_files:
        payload["reasons"] = sorted(set(payload["reasons"]))
    affected_files.sort(key=lambda item: (-int(item.get("_sort_score", 0)), item["file"]))
    for payload in affected_files:
        payload.pop("_sort_score", None)
    affected_files = affected_files[:max_results]
    affected_symbols = affected_symbols[:max_results]

    tracked_files = ctx.structural_store.list_tracked_files(project_root)
    candidate_tests = (
        _candidate_tests(
            ctx,
            project_root,
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