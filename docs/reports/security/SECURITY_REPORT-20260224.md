# Security Review — code-intel MCP Server (Post-Remediation Delta)

**Reviewer:** Senior Security Engineer (automated)
**Date:** 2026-02-24
**Scope:** All code changes since `SECURITY_REPORT-20260223` remediation (commits `5afec29..e5e1f91`, 13 commits, ~800 insertions)
**Changed Files:** `server.py`, `parser.py`, `linker.py`, `storage.py`, `utils.py`, `config.py`, `.env`, `.env-example`
**Previous Report:** [SECURITY_REPORT-20260223.md](file:///d:/Development/code-intel/docs/security/SECURITY_REPORT-20260223.md)

---

## Executive Summary

This is a **delta security review** following the full remediation of 7 findings from the initial audit. The codebase underwent significant refactoring post-remediation — including a new hybrid keyword search system, overhauled `find_definition`/`find_references` logic with AST-based resolution streams, new `VectorStore` query methods, new path normalization utilities, and an embedding model change.

### Previous Remediation Status: ✅ ALL INTACT

All 7 remediated findings from the previous report were verified as still correctly applied:

| Original Finding | Status | Verification |
|---|---|---|
| FINDING-1: SQL/Filter Injection | ✅ Intact | `_sanitize_filter_value()` applied on all 6 LanceDB filter sites (4 original + 2 new) |
| FINDING-2: Unsafe `pickle` | ✅ Intact | `json.dumps/loads` with proactive binary blob detection in `cache.py` |
| FINDING-3: Git Subprocess Env | ✅ Intact | `_GIT_ENV` with `GIT_TERMINAL_PROMPT=0` applied to all 3 functions |
| FINDING-4: Path Traversal | ✅ Intact | `_is_within_root()` containment check in all 3 import resolvers |
| FINDING-5: MD5 → SHA-256 | ✅ Intact | SHA-256 used in `parser.py:358`, `storage.py:40`, `cache.py:46` |
| FINDING-6: `.lancedb/` in `.gitignore` | ✅ Intact | Present at line 22 of `.gitignore` |
| FINDING-7: `datetime.utcnow()` | ✅ Intact | `datetime.now(timezone.utc)` used in `cache.py:70,99` and `storage.py:300` |

### New Findings: 4 (0 HIGH, 2 MEDIUM, 2 LOW)

The refactoring did **not** introduce any high-severity issues. The codebase is in a stronger security posture than the previous audit cycle. However, 4 new findings were identified:

| Severity | Count |
|----------|-------|
| 🔴 HIGH  | 0     |
| 🟡 MEDIUM | 2    |
| 🟢 LOW   | 2     |

---

## New Findings

### 🟡 FINDING-8: LIKE Wildcard Injection in New Text Search Methods

**File:** [storage.py](file:///d:/Development/code-intel/src/storage.py)
**Lines:** 148, 164

Two new methods were added post-remediation that use `LIKE` operators with `_sanitize_filter_value()`:

```python
# storage.py:148
results = table.search().where(f'content LIKE "%{safe_query}%"').to_list()

# storage.py:164
results = table.search().where(f'content LIKE "%{safe_query}%"').to_list()
```

**Issue:** While `_sanitize_filter_value()` correctly escapes double-quotes and blocks SQL keywords, it does **not** escape LIKE wildcard characters (`%` and `_`). A caller providing a `symbol_name` or `query_text` containing `%` or `_` could:
- `%` — match any sequence of characters (broader matches than intended)
- `_` — match any single character (broader matches than intended)

**Risk:** Data leakage through broader-than-expected search results. Not exploitable for write operations since `LIKE` is read-only, but could cause an MCP consumer to receive chunks from unrelated files.

**Impact:** Low in practice — this is a local tool and the attack vector requires a malicious MCP caller. However, it's a defense-in-depth gap for the filter sanitization layer.

**Recommendation:**
Extend `_sanitize_filter_value()` to escape LIKE wildcards when the value will be used in a LIKE clause, or create a dedicated `_sanitize_like_value()`:

```python
def _sanitize_like_value(value: str) -> str:
    """Escapes LIKE wildcards in addition to standard filter sanitization."""
    sanitized = _sanitize_filter_value(value)
    return sanitized.replace('%', '\\%').replace('_', '\\_')
```

---

### 🟡 FINDING-9: Regex Extraction in `search_code_impl` — Potential ReDoS Surface

**File:** [server.py](file:///d:/Development/code-intel/src/server.py)
**Lines:** 244-245

A new hybrid recall enhancement was added that runs a regex against the user's search query:

```python
import re
keywords = re.findall(r'\b[A-Z]{3,}\b|\b[A-Za-z]{6,}\b', query)
```

**Risk (ReDoS):** This specific pattern is non-vulnerable to ReDoS because it uses simple alternation with anchored `\b` word boundaries and no quantifier nesting. The regex engine will not backtrack exponentially. **No immediate ReDoS risk exists.**

**Risk (Information Disclosure via Keyword Injection):** The extracted keywords are used to perform literal text searches across *all* indexed content:

```python
for kw in keywords[:3]:
    text_results = vector_store.find_chunks_containing_text(project_root, kw, limit=keyword_limit)
```

A crafted query like `"search CORS authentication database_password"` would execute keyword searches for `CORS`, `authentication`, and `database_password`, potentially surfacing code chunks containing those strings even if they weren't semantically relevant.

**Impact:** Low — this is a developer tool where the user already has access to the code. But it represents an unintended broadening of search scope. The `keywords[:3]` cap is a good mitigation.

**Recommendation:**
- Consider limiting keyword search to a defined set of chunk types (source code, not config files) or exclude chunks with `language: 'yaml'` / `language: 'json'` from keyword results to reduce exposure of configuration values.
- Document the hybrid search behavior so MCP consumers are aware that queries may be decomposed into keyword sub-searches.

---

### 🟢 FINDING-10: Missing Input Validation on `limit` Parameter

**File:** [server.py](file:///d:/Development/code-intel/src/server.py)
**Lines:** 229, 236

The `search_code_impl` function accepts a `limit` parameter with no upper bound validation:

```python
async def search_code_impl(query: str, root_path: str = ".", limit: int = 10, ...):
    fetch_limit = limit * 5 if (include or exclude) else limit
    ...
    results = vector_store.search(project_root_str, query_vec, limit=fetch_limit)
```

**Risk:** A caller providing `limit=10000` with include/exclude patterns would trigger `fetch_limit=50000`, potentially causing LanceDB to return an excessive amount of data and consume significant memory.

**Impact:** Local DoS only — the MCP transport is local `stdio`. An adversarial caller could degrade IDE performance but not gain unauthorized access.

**Recommendation:**
Add a bounds check:
```python
limit = max(1, min(limit, 100))  # Clamp to [1, 100]
```

---

### 🟢 FINDING-11: `.env-example` Missing Secret Warning Comment

**File:** [.env-example](file:///d:/Development/code-intel/.env-example)

The original FINDING-6 recommended adding a comment in `.env-example` warning future contributors not to put secrets in `.env`. The current `.env-example` does not include this warning.

```
# --- Embedding Configuration ---
# Specialized code embedding model (Recommended for RAG/KG quality)
EMBEDDING_MODEL=unclemusclez/jina-embeddings-v2-base-code
```

**Risk:** Informational only. A future contributor might add API keys, database credentials, or authentication tokens to the `.env` file without understanding the risk.

**Recommendation:**
Add a prominent warning at the top of `.env-example`:
```
# ⚠️ WARNING: Do NOT put secrets (API keys, passwords, tokens) in this file.
# This file is for local tool configuration only. See docs for secret management.
```

---

## OWASP Top 10 Reassessment

| # | OWASP Category | Previous | Current | Delta |
|---|---|---|---|---|
| A01 | Broken Access Control | ⚠️ Partial | ⚠️ Partial | No change — acceptable for local tool |
| A02 | Cryptographic Failures | ⚠️ Yes | ✅ Clean | MD5 → SHA-256 ✅, pickle → json ✅ |
| A03 | Injection | 🔴 Yes | 🟡 Partial | SQL filter injection fixed ✅. New LIKE wildcard gap (FINDING-8) |
| A04 | Insecure Design | ✅ N/A | ✅ N/A | — |
| A05 | Security Misconfiguration | ✅ Clean | ✅ Clean | `.env` properly gitignored |
| A06 | Vulnerable Components | ✅ N/A | ✅ N/A | `fastmcp` version pinned (`pyproject.toml`) |
| A07 | Auth Failures | ✅ N/A | ✅ N/A | — |
| A08 | Data Integrity Failures | ⚠️ Yes | ✅ Clean | pickle eliminated ✅ |
| A09 | Logging/Monitoring | ✅ Adequate | ✅ Adequate | — |
| A10 | SSRF | ⚠️ Bounded | ⚠️ Bounded | Ollama endpoint remains env-controlled. Embedding model changed to `jina-embeddings-v2-base-code` — no new SSRF surface |

---

## Security Posture Changes

### Improvements Since Previous Report

1. **New `normalize_path()` utility** (`utils.py`): Centralizes path normalization with Windows drive letter lowercasing. This reduces hash/lookup mismatches and eliminates an entire class of path confusion bugs.

2. **AST-based definition resolution** (`server.py:385-503`): The new `_find_definition` and `_find_references` methods use deterministic AST mapping via the knowledge graph. This is a security improvement because:
   - It reduces reliance on string pattern matching for symbol resolution
   - It uses the `_get_file_priority()` helper to deprioritize documentation over source code, reducing potential for misleading results

3. **Language-scoped symbol linking** (`linker.py:92`): Global fallback searches now filter by language (`t.get("language") == lang`), preventing cross-language symbol collisions from polluting results.

4. **Decorator sanitization** (`linker.py:44`): Decorator names are stripped of `@`, split by `.`, and only the last component is used. This prevents crafted decorator strings from being used as full symbol lookup queries.

### Areas of Concern

1. **Broadened search surface**: The hybrid keyword search (`server.py:241-256`) and two new storage methods (`find_chunks_containing_text`, `find_chunks_with_usage`) significantly expand the query surface area. While each individually uses `_sanitize_filter_value()`, the LIKE wildcard gap (FINDING-8) means the sanitization is incomplete for these specific use cases.

2. **Inline `import re`** (`server.py:244`): While functionally harmless, inline imports inside hot paths (`search_code_impl`) can obscure dependency tracking. This is a code quality observation, not a security finding.

---

## Prioritized Remediation Roadmap

| Priority | Finding | Effort | Risk Reduction |
|----------|---------|--------|----------------|
| 1 | FINDING-8: LIKE wildcard escape | ~15 min | Closes injection gap in new filter sites |
| 2 | FINDING-10: `limit` parameter bounds | ~5 min | Prevents local resource exhaustion |
| 3 | FINDING-9: Keyword search documentation | ~10 min | Transparency for MCP consumers |
| 4 | FINDING-11: `.env-example` warning | ~1 min | Developer awareness |

---

## Conclusion

The post-remediation code changes **did not introduce any high-severity vulnerabilities**. All 7 previous remediations remain correctly applied and were not regressed during the refactoring.

The 4 new findings are low-to-medium severity and are consistent with defense-in-depth improvements rather than active exploit vectors. The most actionable item is **FINDING-8** (LIKE wildcard escaping), which is a natural extension of the sanitization framework already in place.

Overall risk rating: **LOW** — improved from **MEDIUM** in the previous report. The security posture has materially strengthened through the remediation cycle and subsequent refactoring.
