"""
tools/search.py — search_code tool implementation.

Provides:
    search_code_impl: Hybrid semantic + keyword search over the vector index.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Tuple

from ..context import AppContext
from ..indexer import _should_process_file
from ..utils import normalize_path

logger = logging.getLogger("server")

_MAX_SEARCH_LIMIT = 50

_GENERATED_FILENAME_PATTERNS = (
    "generatedpluginregistrant.",
    ".g.dart",
    ".freezed.dart",
)

_GENERATED_PATH_PARTS = {
    "build",
    "generated",
    ".dart_tool",
    "ephemeral",
}


def _classify_result_type(filename: str) -> str:
    normalized = filename.replace("\\", "/").lower()
    path = Path(normalized)

    if "docs/reports/" in normalized:
        return "report"
    if normalized.endswith(".md") or normalized.startswith("docs/"):
        return "docs"
    if any(part in {"tests", "test"} for part in path.parts):
        return "test"
    return "source"


def _is_generated_artifact(filename: str) -> bool:
    normalized = filename.replace("\\", "/").lower()
    path = Path(normalized)

    if any(part in _GENERATED_PATH_PARTS for part in path.parts):
        return True

    return any(pattern in normalized for pattern in _GENERATED_FILENAME_PATTERNS)


def _classify_query_intent(query: str) -> str:
    lowered = query.lower()
    documentation_terms = {
        "docs", "documentation", "report", "readme", "architecture", "design", "security review"
    }
    framework_terms = {
        "depends", "middleware", "router", "provider", "riverpod", "fastapi", "decorator"
    }
    implementation_terms = {
        "function", "class", "implementation", "endpoint", "service", "method", "provider"
    }

    if any(term in lowered for term in documentation_terms):
        return "documentation"
    if any(term in lowered for term in framework_terms):
        return "framework"
    if any(term in lowered for term in implementation_terms):
        return "implementation"
    return "general"


def _semantic_relevance_score(result: Dict, semantic_rank: int) -> float:
    distance = result.get("_distance")
    if distance is not None:
        try:
            return -float(distance)
        except (TypeError, ValueError):
            pass
    return float(-semantic_rank)


def _result_bias_score(result: Dict, query_intent: str, semantic_rank: int) -> Tuple[int, float, int, int, int]:
    result_type = _classify_result_type(result.get("filename", ""))
    type_scores = {
        "implementation": {"source": 4, "test": 3, "docs": 1, "report": 0},
        "framework": {"source": 4, "test": 3, "docs": 1, "report": 0},
        "general": {"source": 3, "test": 2, "docs": 1, "report": 0},
        "documentation": {"docs": 4, "report": 3, "source": 2, "test": 1},
    }
    bias = type_scores.get(query_intent, type_scores["general"])
    return (
        0 if _is_generated_artifact(result.get("filename", "")) else 1,
        bias.get(result_type, 0),
        _semantic_relevance_score(result, semantic_rank),
        1 if bool(result.get("symbol_name")) else 0,
        -int(result.get("start_line", 0) or 0),
    )


def _dedupe_results(results: Iterable[Dict]) -> list[Dict]:
    deduped = []
    seen_ids = set()
    for result in results:
        result_id = result.get("id")
        if result_id and result_id in seen_ids:
            continue
        if result_id:
            seen_ids.add(result_id)
        deduped.append(result)
    return deduped


def _rank_results(results: Iterable[Dict], query_intent: str) -> list[Dict]:
    ranked_results = list(results)
    for semantic_rank, result in enumerate(ranked_results):
        result.setdefault("_semantic_rank", semantic_rank)

    ranked_results.sort(
        key=lambda result: _result_bias_score(
            result,
            query_intent,
            int(result.get("_semantic_rank", 0) or 0),
        ),
        reverse=True,
    )
    return ranked_results


async def search_code_impl(
    query: str,
    ctx: AppContext,
    root_path: str = ".",
    limit: int = 10,
    include: str = None,
    exclude: str = None,
) -> str:
    """Perform a semantic search and return a formatted results string."""
    try:
        project_root_str = normalize_path(root_path)
        limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        query_intent = _classify_query_intent(query)

        # Fetch more candidates when filtering is active so we still return `limit` results.
        fetch_limit = limit * 5 if (include or exclude) else limit * 3

        query_vec = await ctx.ollama.get_embedding(query)
        results = ctx.vector_store.search(project_root_str, query_vec, limit=fetch_limit)
        for semantic_rank, result in enumerate(results):
            result.setdefault("_semantic_rank", semantic_rank)

        # --- Hybrid recall enhancement ---
        # Supplement semantic results with literal keyword matches for acronyms / long words.
        keywords = re.findall(r'\b[A-Z]{3,}\b|\b[A-Za-z]{6,}\b', query)
        if keywords:
            keyword_limit = limit // 2
            seen_ids = {r.get('id') for r in results if r.get('id')}
            for kw in keywords[:3]:
                text_results = ctx.vector_store.find_chunks_containing_text(
                    project_root_str, kw, limit=keyword_limit
                )
                for keyword_rank, tr in enumerate(text_results, start=len(results)):
                    tr.setdefault("_semantic_rank", keyword_rank)
                    tr_id = tr.get('id')
                    if tr_id and tr_id not in seen_ids:
                        results.append(tr)
                        seen_ids.add(tr_id)

        results = _dedupe_results(results)
        results = _rank_results(results, query_intent)

        if not results:
            return f"No matching code found in project: {project_root_str}"

        # Apply scope filters and cap at `limit`
        filtered_results = []
        for r in results:
            if _should_process_file(r['filename'], project_root_str, include, exclude):
                filtered_results.append(r)
                if len(filtered_results) >= limit:
                    break

        if not filtered_results:
            return f"No matches found after applying filters (fetched {len(results)} candidates)."

        output = [f"Results for project: {project_root_str}\n"]
        for r in filtered_results:
            meta = []
            meta.append(f"Result Type: {_classify_result_type(r.get('filename', ''))}")
            meta.append(f"Query Intent: {query_intent}")
            if r.get('author'):
                meta.append(f"Author: {r['author']}")
            if r.get('last_modified'):
                meta.append(f"Date: {r['last_modified']}")
            if r.get('dependencies') and r['dependencies'] != "[]":
                meta.append(f"Deps: {r['dependencies']}")

            meta_str = "\n".join(meta) + "\n" if meta else ""
            output.append(
                f"File: {r['filename']} ({r['start_line']}-{r['end_line']})\n"
                f"Symbol: {r.get('symbol_name', 'N/A')}\n"
                f"Complexity: {r.get('complexity', 0)}\n"
                f"{meta_str}"
                f"Content:\n```\n{r['content']}\n```\n"
            )
        return "\n---\n".join(output)

    except Exception as e:
        return f"Search failed: {e}"
