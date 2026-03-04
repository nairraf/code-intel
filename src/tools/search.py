"""
tools/search.py — search_code tool implementation.

Provides:
    search_code_impl: Hybrid semantic + keyword search over the vector index.
"""

import re
import logging
from pathlib import Path

from ..context import AppContext
from ..indexer import _should_process_file
from ..utils import normalize_path

logger = logging.getLogger("server")


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

        # Fetch more candidates when filtering is active so we still return `limit` results.
        fetch_limit = limit * 5 if (include or exclude) else limit

        query_vec = await ctx.ollama.get_embedding(query)
        results = ctx.vector_store.search(project_root_str, query_vec, limit=fetch_limit)

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
                for tr in text_results:
                    tr_id = tr.get('id')
                    if tr_id and tr_id not in seen_ids:
                        results.append(tr)
                        seen_ids.add(tr_id)

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
