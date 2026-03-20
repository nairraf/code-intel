from .structural_common import build_freshness, edge_confidence, parse_edge_metadata
from ..utils import normalize_path


_NON_DEFINITION_KINDS = {"import_statement", "import_from_statement"}


async def inspect_symbol_impl(
    root_path: str,
    symbol_name: str,
    ctx,
    filename: str | None = None,
    line: int | None = None,
    include_references: bool = True,
    include_dependents: bool = False,
    max_references: int = 50,
) -> dict:
    project_root = normalize_path(root_path)
    normalized_filename = normalize_path(filename) if filename else None

    warnings: list[str] = []
    freshness, freshness_warnings = await build_freshness(project_root, ctx)
    warnings.extend(freshness_warnings)

    definitions = ctx.structural_store.find_symbols(project_root, symbol_name, normalized_filename)
    if line is not None and definitions:
        line_matches = [record for record in definitions if record.start_line <= line <= record.end_line]
        if line_matches:
            definitions = line_matches
    if not definitions and normalized_filename is not None:
        definitions = ctx.structural_store.find_symbols(project_root, symbol_name)

    concrete_definitions = [record for record in definitions if record.symbol_kind not in _NON_DEFINITION_KINDS]
    if concrete_definitions:
        definitions = concrete_definitions

    definition_payload = [
        {
            "file": record.filename,
            "startLine": record.start_line,
            "endLine": record.end_line,
            "language": record.language,
            "confidence": "exact",
            "evidence": [],
        }
        for record in definitions
    ]

    references: list[dict] = []
    if include_references and definitions:
        incoming_edges = ctx.structural_store.list_incoming_edges(
            project_root,
            [record.symbol_id for record in definitions],
            edge_kind="call",
        )
        seen: set[tuple[str, int, str, str]] = set()
        for edge in incoming_edges:
            metadata = parse_edge_metadata(edge)
            line_number = int(metadata.get("line", 0) or 0)
            kind = metadata.get("context", edge.edge_kind)
            match_type = metadata.get("match_type", "exact")
            key = (edge.source_filename, line_number, edge.target_symbol_id, kind)
            if key in seen:
                continue
            seen.add(key)
            confidence = edge_confidence(match_type)
            references.append(
                {
                    "file": edge.source_filename,
                    "line": line_number,
                    "kind": kind,
                    "confidence": confidence,
                    "evidence": [
                        {
                            "kind": kind,
                            "reason": f"Exact structural edge to '{symbol_name}' via {match_type}.",
                            "source": edge.source_filename,
                            "line": line_number,
                            "confidence": confidence,
                        }
                    ],
                }
            )
        references.sort(key=lambda item: (item["file"], item["line"], item["kind"]))
        references = references[:max_references]

    if include_dependents and not include_references:
        warnings.append("include_dependents currently maps to structural references on the new core.")

    if not definition_payload:
        warnings.append(f"No exact structural definition found for '{symbol_name}'.")

    return {
        "status": "ok",
        "freshness": freshness,
        "symbol": symbol_name,
        "definitions": definition_payload,
        "references": references,
        "warnings": warnings,
    }