# Code-Intel MCP Tool Evaluation Report

**Date:** 2026-03-09 (Retest after code-intel update)  
**Assessor:** Antigravity  
**Index:** Full Rebuild — 109 files, 364 chunks  
**Active Branch:** `development`  
**Previous Reports:** 2026-03-09 (pre-update), 2026-03-07

---

## Executive Summary

Fourth-pass benchmark completed after a code-intel engine update and forced full reindex. Key metrics:

| Metric | Prior Run | This Run | Change |
|---|---|---|---|
| Total Chunks | 319 | 364 | +14% |
| Python Chunks | 50 | **95** | **+90%** |
| Unique Files | 106 | 106 | — |

### Verdict: Both Prior Regressions Fixed ✅

| Issue | Prior Status | Current Status |
|---|---|---|
| `search_code` regression (`GeneratedPluginRegistrant.java` dominating) | ❌ Fail | ✅ **Fixed** — correct targets now rank #1 |
| Python `verify_firebase_token` missing test file references | ⚠️ Partial | ✅ **Fixed** — `tests/test_main.py` now found |

---

## Detailed Results

### Suite 1: Project Pulse / Architecture Stats

**Tool:** `get_stats`  
**Grade: ✅ Pass**

| Metric | Value | Change |
|---|---|---|
| Total Chunks | 364 | +45 |
| Python Chunks | 95 | +45 (90% increase) |
| Avg Complexity | 1.34 | -0.05 |
| Stale Files | 48 | — |

**Dependency Hubs:**
- `package:flutter/material.dart` (111 imports) — unchanged
- `gradient_scaffold.dart` (78 imports) — unchanged
- `glass_card.dart` (74 imports) — unchanged
- `selos_theme.dart` (67 imports) — unchanged
- `app.config` (58 imports) — **NEW**: Python config module now detected as a hub, replacing `flutter_riverpod`

> [!TIP]
> The Python config module (`app.config`) appearing as a dependency hub is correct — it's imported by every Python source file via the `settings` singleton. This was previously invisible and is now properly tracked.

---

### Suite 2: Definition Lookups

**Tool:** `find_definition`

#### 2A — `ApiService` (Dart)
**Grade: ✅ Pass** — `api_service.dart:6`, exact match. Unchanged.

---

### Suite 3: Reference Tracing

#### 3A — `APIRouter` (Python Backend)
**Grade: ✅ Pass** — Now returns `analysis.py:10` with `call` reference kind. No documentation noise. Clean single result.

| | Prior | Current |
|---|---|---|
| `analysis.py:10` | Fallback Search + doc noise | ✅ Low Confidence, `call` (no noise) |

#### 3B — `GlassCard` (Dart Frontend)
**Grade: ✅ Pass** — All usages found at High Confidence. Unchanged.

#### 3C — `verify_firebase_token` (Python DI + Tests)
**Grade: ✅ Pass — Improved**

| Source | Prior | Current |
|---|---|---|
| `analysis.py:17` (Depends() injection) | ✅ Medium, `dependency_injection` | ✅ Medium, `dependency_injection` |
| `analysis.py:3` (import) | ❌ Not found | ✅ **Low Confidence, `import`** |
| `tests/test_main.py:4` (import) | ❌ Not found | ✅ **Low Confidence, `import`** |

> [!IMPORTANT]
> The test file `tests/test_main.py` is now indexed and its reference to `verify_firebase_token` at line 4 is found. This was the key Python reference recall gap from the prior evaluation.

**Remaining gap:** `tests/test_main.py:16` (the `dependency_overrides[verify_firebase_token]` usage) is not surfaced — this is a dynamic dictionary key lookup that would require deeper AST analysis. Not a practical concern for most workflows.

#### 3D — `LoginScreen` (Dart Widget)
**Grade: ✅ Pass** — `auth_gate.dart:19` at High Confidence. Unchanged.

---

### Suite 4: Semantic Search

**Tool:** `search_code`

#### 4A — "JWT Firebase token validation middleware backend"
**Grade: ✅ Pass — Fixed**

| Rank | Result | Prior Rank |
|---|---|---|
| **1** | **`firebase_auth.py` → `verify_firebase_token`** | 6th |
| 2 | `analysis.py:3` → `verify_firebase_token` import | Not present |
| 3 | `firestore.rules` | Not ranked |
| 4 | `api_service.dart` | 5th |
| 5 | `auth_service.dart` | 4th |

`GeneratedPluginRegistrant.java` **no longer appears in the top 10**. The correct target is now rank #1 with the import reference at rank #2.

#### 4B — "API URL provider configuration"
**Grade: ✅ Pass — Fixed**

| Rank | Result | Prior Rank |
|---|---|---|
| **1** | **`api_providers.dart` → `apiBaseUrlProvider`** | 9th |
| **2** | **`api_providers.dart` → `apiServiceProvider`** | Not in top 10 |
| 3 | `analysis.py:10` → `router = APIRouter()` | Not present |
| 4 | `main.py:9` → `app = FastAPI(...)` | Not present |
| 5 | `config.py` → `Settings` | Not present |

Both target providers are now ranked #1 and #2, with highly relevant backend configuration results following. `GeneratedPluginRegistrant.java` **no longer appears**.

---

## Updated Scorecard

| Module | Status | Precision | Hallucination Risk | Practical Value | Trend |
|---|---|---|---|---|---|
| `get_stats` | ✅ Pass | High | Low | High | ↔ Stable |
| `find_definition` | ✅ Pass | High | Low | High | ↔ Stable |
| `find_references` (Dart) | ✅ Pass | High | Low | High | ↔ Stable |
| `find_references` (Python) | ✅ Pass | Medium-High | Low | **High** | **↑ Improved** |
| `search_code` | ✅ Pass | **High** | **Low** | **High** | **↑↑ Fixed** |

---

## Comparison: Prior vs Current

| Module | Prior Grade | Current Grade | Change |
|---|---|---|---|
| `get_stats` | ✅ Pass | ✅ Pass | — |
| `find_definition` | ✅ Pass | ✅ Pass | — |
| `find_references` (Dart) | ✅ Pass | ✅ Pass | — |
| `find_references` (Python) | ⚠️ Partial | ✅ Pass | ↑ test files now indexed |
| `search_code` | ❌ Fail | ✅ Pass | ↑↑ auto-gen noise eliminated, correct ranking |

---

## What Changed

1. **Python indexing depth nearly doubled** (50→95 chunks): The indexer now produces finer-grained chunks for Python files, capturing individual imports, assignments, and function-level symbols that were previously rolled into coarser chunks.

2. **Auto-generated file ranking fixed**: `GeneratedPluginRegistrant.java` no longer dominates semantic search. It appears the engine now properly weights code relevance over raw complexity scores.

3. **Python test directory coverage**: `tests/test_main.py` is now indexed with structural references, closing the test-file recall gap.

4. **Python config dependency tracking**: `app.config` now appears as a dependency hub (58 imports), showing improved Python import graph resolution.

---

## Remaining Action Items

| Priority | Item | Status |
|---|---|---|
| ~~🔴 High~~ | ~~Auto-generated file noise in search_code~~ | ✅ Fixed |
| ~~🟡 Medium~~ | ~~Index Python tests/ directory~~ | ✅ Fixed |
| 🟢 Low | Promote `verify_firebase_token` Depends() from Medium → High confidence | Open |
| 🟢 Low | Surface dynamic dict-key references (e.g., `dependency_overrides[symbol]`) | Open |

---

## Final Recommendation

**All five code-intel modules now grade as ✅ Pass.** The tool is production-ready as a primary navigation and discovery layer for both Dart and Python codebases. The two-step grep validation workflow is still recommended for edge cases involving dynamic Python patterns, but is **no longer required** for routine symbol lookup and semantic search.

---

*This report supersedes all prior evaluations (2026-03-07, 2026-03-09 pre-update).*
