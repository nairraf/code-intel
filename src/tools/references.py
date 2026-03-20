"""
tools/references.py — find_references tool implementation.

Provides:
    find_references_impl: Traces all call-site references for a named symbol.
"""

import logging
from typing import Optional

from ..utils import normalize_path
from ..context import AppContext
from .definition import _get_file_priority, _rank_chunk_key

logger = logging.getLogger("server")


def _normalize_reference_confidence(match_type: str, context: str) -> str:
    if match_type == "explicit_import":
        return "High"
    if context in {"dependency_injection", "decorator", "instantiation"}:
        return "Medium"
    return "Low"


def _reference_kind(context: str) -> str:
    mapping = {
        "import": "import",
        "dependency_injection": "dependency_injection",
        "decorator": "decorator",
        "instantiation": "instantiation",
        "override_registration": "override_registration",
        "call": "call",
    }
    return mapping.get(context, context or "unknown")


async def find_references_impl(
    symbol_name: str,
    root_path: str,
    ctx: AppContext
) -> str:
    """Find all references to a symbol within the project.

    Strategy:
        1. Locate definition chunk(s) in the vector store.
        2. Walk Knowledge Graph edges to find calling sites.
        3. Fallback: direct usage search when symbol is external/unlinked.
    """
    try:
        project_root_str = normalize_path(root_path)

        # --- Strategy 1: Definition-anchored edge traversal ---
        def_chunks = ctx.vector_store.find_chunks_by_symbol(project_root_str, symbol_name)
        if not def_chunks:
            # --- Fallback: direct usage search ---
            usage_chunks = ctx.vector_store.find_chunks_with_usage(project_root_str, symbol_name)
            if not usage_chunks:
                return f"Symbol '{symbol_name}' not found locally or in project usages."

            usage_chunks.sort(key=lambda x: _rank_chunk_key(x), reverse=True)
            all_refs = [
                f"Referenced (external/unlinked) in {c['filename']} "
                f"at line {c['start_line']} (Fallback Search)\n"
                f"Chunk: {c.get('symbol_name', 'N/A')}"
                for c in usage_chunks
            ]
            return "\n---\n".join(all_refs)

        all_refs = []
        for d in def_chunks:
            edges = ctx.knowledge_graph.get_edges(
                target_id=d["id"],
                type="call",
                project_root=project_root_str,
            )
            for edge in edges:
                source_id, _, _, meta = edge
                source_chunk = ctx.vector_store.get_chunk_by_id(project_root_str, source_id)
                if source_chunk:
                    match_type = meta.get("match_type", "unknown")
                    context = meta.get("context", "N/A")
                    confidence = _normalize_reference_confidence(match_type, context)
                    reference_kind = _reference_kind(context)
                    all_refs.append({
                        "priority": _get_file_priority(source_chunk["filename"]),
                        "text": (
                            f"Referenced in {source_chunk['filename']} "
                            f"at line {meta.get('line', '??')} "
                            f"({confidence} Confidence: {match_type})\n"
                            f"Reference Kind: {reference_kind}\n"
                            f"Context: {context}"
                        ),
                    })

        if not all_refs:
            return (
                f"Symbol '{symbol_name}' found at {def_chunks[0]['filename']} "
                f"L{def_chunks[0]['start_line']}, but no references were discovered "
                f"in the knowledge graph."
            )

        all_refs.sort(key=lambda x: x["priority"], reverse=True)
        return "\n---\n".join(r["text"] for r in all_refs)

    except Exception as e:
        return f"Error finding references: {e}"
