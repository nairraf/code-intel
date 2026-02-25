# Code Quality Review — code-intel

> **Reviewer role:** Senior Developer
> **Date:** 2026-02-24
> **Scope:** All 16 source files under `src/`

---

## Executive Summary

The codebase is well-structured overall — good separation between parsing, storage, embedding, linking, and resolution. However, several areas have accumulated technical debt from rapid feature iteration and successive security remediations. Below are **12 actionable findings**, ordered by severity: 🔴 High → 🟡 Medium → 🟢 Low.

---

## 🔴 High Priority

### 1. God Module: `server.py` (577 lines, 21 functions)

[server.py](file:///d:/Development/code-intel/src/server.py) mixes **four unrelated concerns**:

| Concern | Functions |
|---------|-----------|
| MCP tool registration | `refresh_index`, `search_code`, `get_stats`, `find_definition`, `find_references` |
| Indexing orchestration | `refresh_index_impl`, `process_file_pass1/2` |
| Definition resolution | `_find_definition`, `_get_file_priority` |
| Reference resolution | `_find_references` |

**Impact:** Hard to test individual concerns; every change risks breaking something unrelated.

**Recommended refactoring:**

```
src/
  server.py              → thin MCP tool registration only (~100 lines)
  indexer.py             → refresh_index_impl + file processing
  tools/
    definition.py        → _find_definition + _get_file_priority
    references.py        → _find_references
    search.py            → search_code_impl
    stats.py             → get_stats_impl
```

---

### 2. Duplicated Sorting/Priority Logic (DRY Violation)

The **exact same sorting lambda** appears **5 times** across `_find_definition` and `_find_references`:

```python
# Lines 443-445, 460-462, 481-483, 492-494 in server.py, line 539
key=lambda x: (x.get("language") == source_lang, _get_file_priority(x["filename"]))
```

**Fix:** Extract into a shared `rank_candidates(candidates, source_lang)` function.

---

### 3. Module-Level Global Singletons in `server.py`

```python
# Lines 42-47 — instantiated at import time
parser = CodeParser()
ollama_client = OllamaClient()
vector_store = VectorStore()
knowledge_graph = KnowledgeGraph()
linker = SymbolLinker(vector_store, knowledge_graph)
```

**Problems:**
- **Untestable:** You cannot inject mocks without monkey-patching.
- **Side effects on import:** Database connections, HTTP clients, and SQLite dbs are all opened the moment the module is loaded.
- **No lifecycle management:** `OllamaClient.aclose()` is never called.

**Fix:** Use a simple DI container or factory function:
```python
class AppContext:
    def __init__(self):
        self.parser = CodeParser()
        self.ollama = OllamaClient()
        self.vector_store = VectorStore()
        self.knowledge_graph = KnowledgeGraph()
        self.linker = SymbolLinker(self.vector_store, self.knowledge_graph)
    
    async def close(self):
        await self.ollama.aclose()
```

---

## 🟡 Medium Priority

### 4. `KnowledgeGraph` Opens a New SQLite Connection Per Call

Every `add_edge()`, `get_edges()`, and `clear()` call does:
```python
with sqlite3.connect(self.db_path) as conn:
```

**Impact:** Connection overhead on every operation, and no connection pooling. During Pass 2 linking, this is called once per usage per chunk — potentially thousands of times.

**Fix:** Use a persistent connection or a connection pool with proper thread-safety.

---

### 5. Pass 2 Re-Parses Every File

In [server.py L179-189](file:///d:/Development/code-intel/src/server.py#L179-L189), every file is parsed **a second time** to link usages:

```python
# "We re-parse to get the usages (since we don't store them in DB yet)"
chunks = parser.parse_file(filepath, project_root=project_root_str)
```

**Impact:** Doubles parse time for every index operation. For large projects, this is a significant performance bottleneck.

**Fix:** Cache the parsed chunks from Pass 1 in memory and reuse them in Pass 2, or store usages in the DB alongside chunks.

---

### 6. `_recursive_chunk` Is Spaghetti (~90 lines, complexity 111)

[parser.py L179-269](file:///d:/Development/code-intel/src/parser.py#L179-L269) is the **most complex function in the codebase** (complexity score: 111 per `get_stats`). It contains:
- Nested `if lang == "python"` / `if lang == "dart"` blocks with deeply nested parent-type checks
- Magic conditions like `node.parent.type == "module" if node.type == "expression_statement" else ...`
- Duplicate logic for Python and Dart scoping

**Fix:** Extract language-specific scoping rules into a Strategy pattern:
```python
class PythonScopingStrategy:
    def is_global_target(self, node) -> bool: ...

class DartScopingStrategy:
    def is_global_target(self, node) -> bool: ...
```

---

### 7. `_extract_usages` Handles Two Different Return Types

[parser.py L546-580](file:///d:/Development/code-intel/src/parser.py#L546-L580) has two nearly identical code paths:

```python
if isinstance(captures, list):      # Standard tree-sitter
    for node, tag in captures: ...
elif isinstance(captures, dict):    # Legacy/other bindings
    for tag, nodes in captures.items(): ...
```

The logic inside each branch is **identical** (same `SymbolUsage` construction, same context inference).

**Fix:** Normalize `captures` to a single format at the top of the function, then process once.

---

### 8. Inline Import Inside Hot Path

[server.py L244](file:///d:/Development/code-intel/src/server.py#L244):
```python
import re  # inside search_code_impl
```

And [storage.py L81](file:///d:/Development/code-intel/src/storage.py#L81):
```python
import json  # inside upsert_chunks
```

And [storage.py L278-280](file:///d:/Development/code-intel/src/storage.py#L278-L280):
```python
from collections import Counter  # inside get_detailed_stats
from datetime import datetime, timezone
import json
```

**Fix:** Move all imports to module level. Python caches module imports, but the repeated lookup is still a code smell and makes dependency analysis harder.

---

## 🟢 Low Priority

### 9. Bare `except` and Silent Exception Swallowing

Multiple locations silently swallow exceptions:

| File | Line(s) | Issue |
|------|---------|-------|
| [parser.py](file:///d:/Development/code-intel/src/parser.py#L64) | 64, 71, 82, 137, 155, 581 | `except Exception: pass` |
| [storage.py](file:///d:/Development/code-intel/src/storage.py#L293) | 293, 306, 326 | `except: pass` (bare except!) |
| [config.py](file:///d:/Development/code-intel/src/config.py#L19) | 19 | Fallback silently reassigns to local var `d` inside a loop, which has no effect |

Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`, which should never be silently swallowed.

**Fix:** At minimum, change `except:` to `except Exception:` and log warnings.

---

### 10. `config.py` Fallback Directory Bug

```python
for d in [VAULT_DIR, LOG_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local
        d = PROJECT_ROOT / ".code_intel_store" / d.name  # ← rebinds loop variable
        d.mkdir(parents=True, exist_ok=True)  # ← creates dir but VAULT_DIR/LOG_DIR unchanged
```

The fallback assigns to the **loop variable** `d`, so `VAULT_DIR` and `LOG_DIR` still point to the original paths that failed. Any downstream code using those constants will still fail.

---

### 11. Repeated Table Existence Checks in `VectorStore`

Nearly every method in `VectorStore` starts with:
```python
table_name = self._get_table_name(project_root)
if table_name not in self.db.table_names():
    return []  # or return {}, return None, return 0
```

This is **10 occurrences** of the same boilerplate.

**Fix:** Extract a `_get_table_or_none()` helper:
```python
def _get_table_or_none(self, project_root: str):
    table_name = self._get_table_name(project_root)
    if table_name not in self.db.table_names():
        return None
    return self.db.open_table(table_name)
```

---

### 12. Duplicate Comment on L529-530 of `server.py`

```python
# 2. Fallback: Symbol might be external (e.g., FastAPI Depends, decorators). 
# 2. Fallback: Symbol might be external (e.g., FastAPI Depends, decorators).
```

Simple copy-paste artifact.

---

## Summary Matrix

| # | Finding | Severity | Effort | Impact | Status (2026-02-24) |
|---|---------|----------|--------|--------|---------------------|
| 1 | God module `server.py` | 🔴 | Large | Testability, maintainability | ❌ Open — still 576 lines |
| 2 | Duplicated sorting lambda ×5 | 🔴 | Small | DRY, bug risk | ❌ Open — 5 occurrences of `_get_file_priority` lambda remain |
| 3 | Global singleton instantiation | 🔴 | Medium | Testability, lifecycle | ❌ Open — module-level globals unchanged |
| 4 | SQLite connection-per-call | 🟡 | Small | Performance | ❌ Open — `knowledge_graph.py` still opens new connection every call |
| 5 | Pass 2 re-parses all files | 🟡 | Medium | Performance | ❌ Open |
| 6 | `_recursive_chunk` spaghetti | 🟡 | Medium | Readability, bug risk | ❌ Open — still ~90 lines, complexity 111 |
| 7 | Dual capture format handling | 🟡 | Small | DRY, readability | ❌ Open — two branches still in `_extract_usages` |
| 8 | Inline imports in hot paths | 🟡 | Trivial | Code clarity | ❌ Open — `server.py:244` (`re`), `storage.py:81,280` (`json`) |
| 9 | Bare/silent exception handling | 🟢 | Small | Debuggability | ✅ **Fixed** — bare `except:` in `storage.py` replaced with `except Exception:` |
| 10 | Config fallback bug | 🟢 | Trivial | Correctness | ❌ Open — loop variable rebinding on `config.py:21` |
| 11 | Repeated table-exists boilerplate | 🟢 | Small | DRY | ❌ Open |
| 12 | Duplicate comment | 🟢 | Trivial | Cleanliness | ❌ Open — `server.py:529-530` |

---

## Re-audit: 2026-02-24

> **Auditor:** Antigravity AI
> **Trigger:** Post-reference-tracking-fix review to assess what changed

### Key Findings

1. **Only item #9 was resolved** by recent work. The bare `except:` patterns in `storage.py` were corrected to `except Exception:`.
2. **Recent work focused on correctness, not structure.** The reference tracking improvements (Dart widget instantiation edges, Python `Depends()` context tagging) added value without touching the structural issues flagged here.
3. **The tool is validated and working well.** An independent MCP evaluation (see `docs/feedback.md`) confirmed high-confidence results for Dart references, correct semantic search, and accurate definition lookups.

### Decision: Backlogged

All remaining items are **deferred** — the tool delivers strong user value in its current form and none of these findings block functionality. The items should be revisited when:

- **Wave 1 triggers:** A contributor session with ~30 min of slack time. Items 2, 8, 10, 11, 12 are mechanical fixes with near-zero regression risk.
- **Wave 2 triggers:** A decision to add significant new tool endpoints to `server.py`, or a need to write comprehensive unit tests against the server layer (DI becomes essential).
- **Wave 3 triggers:** Indexing performance becomes a user complaint on projects with 500+ files, or `_recursive_chunk` needs modification for a new language.

---

## Recommended Approach

1. **Wave 1 — Quick wins (~30 min)** (items 2, 8, 10, 11, 12): Mechanical fixes, low risk, can be done in a single session.
   - **Item 2:** Extract `rank_candidates(candidates, source_lang)` helper to replace the 5 duplicated sorting lambdas.
   - **Item 8:** Move 3 inline imports (`re`, `json`) to module level.
   - **Item 10:** Fix `config.py` loop variable rebinding — reassign to `VAULT_DIR`/`LOG_DIR` directly.
   - **Item 11:** Extract `_get_table_or_none()` helper in `VectorStore`.
   - **Item 12:** Delete duplicate comment on `server.py:529-530`.
2. **Wave 2 — `server.py` decomposition** (items 1, 3): Extract tools into `src/tools/` modules, introduce `AppContext` DI container. Medium risk — requires updating test imports.
3. **Wave 3 — Performance & complexity** (items 4, 5, 6, 7): Persistent SQLite connection in `KnowledgeGraph`, cache parsed chunks between Pass 1 and Pass 2, strategy pattern for `_recursive_chunk`, capture format normalization in `_extract_usages`. Higher risk — needs thorough regression testing.
