"""
tools/definition.py — find_definition tool implementation.

Provides:
    _get_file_priority  : File-type ranking helper (source > docs > artifacts).
    _rank_chunk_key     : Composite sort key for candidate chunks.
    find_definition_impl: Core jump-to-definition logic.
"""

import logging
from pathlib import Path
from typing import Optional

from ..utils import normalize_path
from ..context import AppContext

logger = logging.getLogger("server")


# ---------------------------------------------------------------------------
# Ranking helpers
# ---------------------------------------------------------------------------

def _get_file_priority(filename: str) -> int:
    """Assigns priority score to files: Source > Docs > Artifacts."""
    ext = Path(filename).suffix.lower()
    if ext in ('.py', '.dart', '.ts', '.js', '.go', '.rs', '.java', '.cpp', '.c'):
        return 100
    if ext == '.md':
        return 50
    return 10


def _rank_chunk_key(chunk: dict, source_lang: Optional[str] = None):
    """Returns a sorting key for chunks based on language match and file priority."""
    priority = _get_file_priority(chunk.get("filename", ""))
    if source_lang:
        return (chunk.get("language") == source_lang, priority)
    return priority


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

async def find_definition_impl(
    filename: str,
    line: int,
    ctx: AppContext,
    symbol_name: Optional[str] = None,
    root_path: str = ".",
) -> str:
    """Locate the source-code definition for a symbol.

    Strategy (in priority order):
        1. AST-based resolution via the Knowledge Graph.
        2. Global symbol-name search in the vector store.
        3. Heuristic usage search as a last resort.
    """
    try:
        project_root = normalize_path(root_path)
        filepath = normalize_path(filename)
        source_lang = ctx.parser._get_language(filepath)

        # --- Strategy 1: AST + Knowledge Graph ---
        try:
            chunks = ctx.parser.parse_file(filepath, project_root=project_root)

            target_chunk = None
            target_usages = []

            for chunk in chunks:
                if chunk.start_line <= line <= chunk.end_line:
                    if symbol_name and chunk.symbol_name == symbol_name:
                        return (
                            f"File: {chunk.filename} ({chunk.start_line}-{chunk.end_line})\n"
                            f"Content:\n```\n{chunk.content}\n```"
                        )

                    target_chunk = chunk
                    for usage in chunk.usages:
                        if abs(usage.line - line) <= 1:
                            target_usages.append(usage)
                    break

            if target_chunk and target_usages:
                edges = ctx.knowledge_graph.get_edges(source_id=target_chunk.id, type="call")

                resolved_definitions = []
                for usage in target_usages:
                    target_edge = None
                    for edge in edges:
                        _, target_id, _, meta = edge
                        if meta.get("line") == usage.line or meta.get("match_type") == "name_match":
                            target_edge = edge
                            break

                    if target_edge:
                        _, target_id, _, _ = target_edge
                        def_chunk = ctx.vector_store.get_chunk_by_id(project_root, target_id)
                        if def_chunk:
                            resolved_definitions.append((usage.name, def_chunk))

                # Deduplicate by chunk id
                seen_ids: set = set()
                deduped_defs = []
                for name, dc in resolved_definitions:
                    if dc["id"] not in seen_ids:
                        seen_ids.add(dc["id"])
                        deduped_defs.append((name, dc))

                if deduped_defs:
                    deduped_defs.sort(key=lambda x: _rank_chunk_key(x[1], source_lang), reverse=True)

                    if symbol_name:
                        exact_matches = [dc for name, dc in deduped_defs if name == symbol_name]
                        if exact_matches:
                            deduped_defs = [(symbol_name, dc) for dc in exact_matches]
                        else:
                            global_matches = ctx.vector_store.find_chunks_by_symbol(
                                project_root, symbol_name
                            )
                            if global_matches:
                                global_matches.sort(
                                    key=lambda x: _rank_chunk_key(x, source_lang), reverse=True
                                )
                                deduped_defs = [(symbol_name, g) for g in global_matches]

                    output = []
                    for name, dc in deduped_defs:
                        output.append(
                            f"Jump to '{name}' -> File: {dc['filename']} "
                            f"({dc['start_line']}-{dc['end_line']})\n"
                            f"Content:\n```\n{dc['content']}\n```"
                        )
                    return "\n---\n".join(output)

        except Exception as e:
            logger.error(f"AST-based definition resolution failed: {e}")

        # --- Strategy 2: Global symbol-name search ---
        if symbol_name:
            targets = ctx.vector_store.find_chunks_by_symbol(project_root, symbol_name)
            if not targets:
                # --- Strategy 3: Heuristic usage search ---
                usage_chunks = ctx.vector_store.find_chunks_with_usage(project_root, symbol_name)
                if usage_chunks:
                    usage_chunks.sort(
                        key=lambda x: _rank_chunk_key(x, source_lang), reverse=True
                    )
                    output = []
                    for t in usage_chunks:
                        output.append(
                            f"Heuristic Reference Found -> File: {t['filename']} "
                            f"({t['start_line']}-{t['end_line']})\n"
                            f"Content:\n```\n{t['content']}\n```"
                        )
                    return "\n---\n".join(output)
                return f"No definition or clear usage found for symbol '{symbol_name}'"

            targets.sort(key=lambda x: _rank_chunk_key(x, source_lang), reverse=True)
            output = []
            for t in targets:
                output.append(
                    f"File: {t['filename']} ({t['start_line']}-{t['end_line']})\n"
                    f"Content:\n```\n{t['content']}\n```"
                )
            return "\n---\n".join(output)

        return "Please provide a symbol_name to find its definition if line-based AST mapping fails."

    except Exception as e:
        return f"Error finding definition: {e}"
