# Code-Intel MCP Tool Evaluation Report
Date: 2026-03-07

## Executive Summary
Second-pass benchmark completed without re-index (per request). The index was already fresh and matched `development` HEAD.

Overall verdict:
- Strong for structural navigation (`find_definition`, Dart-heavy `find_references`, project stats).
- Mixed for Python dependency-injection style references (`Depends(...)` surfaced with lower confidence labels).
- Inconsistent for conceptual semantic retrieval (`search_code`) due to documentation-heavy false positives.

Recommended workflow:
- Use `code-intel` first for symbol navigation and architecture awareness.
- Validate with `grep_search` for Python DI edges and semantic queries before making code decisions.

---

## Method
- Ran `mcp_code-intel_get_stats`, `mcp_code-intel_find_definition`, `mcp_code-intel_find_references`, and `mcp_code-intel_search_code`.
- Compared output against literal `grep_search` baselines in `selos_api/app/**`, `selos_api/tests/**`, and `selos_app/lib/**`.
- Graded each module on precision, hallucination rate, and practical speed versus CLI lookup.

---

## Results By Module

### 1) Project Pulse / Stats
Tool: `mcp_code-intel_get_stats`

Observed:
- Reported `279` chunks and `101` files.
- Correctly identified Dart and Python as primary project languages.
- Dependency hubs matched real architecture: `gradient_scaffold.dart`, `glass_card.dart`, `flutter_riverpod`.
- Included actionable metadata: stale file count, rule violations, and index freshness timestamp.

Validation:
- Directory/layout expectations align with workspace structure and known import topology.

Grade:
- Status: Pass
- Precision: High
- Hallucination risk: Low
- Speed vs CLI: Better for high-level architecture views

### 2) Definition Lookup
Tool: `mcp_code-intel_find_definition`

Case A: `ApiService` from `selos_app/lib/core/providers/api_providers.dart:11`
- Returned `selos_app/lib/core/services/api_service.dart:6` (`class ApiService`).
- Baseline check: `grep_search` for `class ApiService` returned same file.

Case B: `verify_firebase_token` from `selos_api/app/routers/analysis.py:6`
- Returned `selos_api/app/middleware/firebase_auth.py:7`.
- Baseline check: `grep_search` confirmed exact definition location.

Grade:
- Status: Pass
- Precision: High
- Hallucination risk: Low
- Speed vs CLI: Better for jump-to-definition tasks

### 3) Reference Tracing
Tool: `mcp_code-intel_find_references`

Case A: `LoginScreen`
- Found structural usage in `selos_app/lib/features/auth/auth_gate.dart:19`.
- Baseline check: `grep_search` confirmed same usage.

Case B: `verify_firebase_token`
- Found `selos_api/app/routers/analysis.py:16` (dependency injection point) with low-confidence tag.
- Baseline check: app-owned references in `selos_api/app/**` and tests in `selos_api/tests/**` were all present.

Case C: `APIRouter`
- Code-intel references were weaker than expected in prior run; `grep_search` in `selos_api/app/**` cleanly resolved import + instantiation in `selos_api/app/routers/analysis.py:1` and `selos_api/app/routers/analysis.py:9`.

Grade:
- Status: Partial
- Precision: High for Dart widgets, Medium for Python DI/framework symbols
- Hallucination risk: Medium (confidence labels vary; can miss framework-context nuance)
- Speed vs CLI: Faster for cross-file Dart UI references; parity/slower confidence for Python DI verification

### 4) Semantic Search
Tool: `mcp_code-intel_search_code`

Query: `JWT Firebase token validation middleware backend`
- Correct top hit: `selos_api/app/middleware/firebase_auth.py:7`.
- Also returned large security docs as high-ranked noise (`docs/reports/security/...`).

Query: `API URL provider configuration`
- Correct hits: `selos_app/lib/core/providers/api_providers.dart:6` and `selos_app/lib/core/providers/api_providers.dart:11`.

Query: `FastAPI router analyze endpoint with Depends verify_firebase_token`
- Mixed quality: relevant router lines surfaced, but non-code documentation appeared prominently.

Query: `Riverpod provider that creates ApiService with base url`
- Correctly surfaced `apiServiceProvider` and `apiBaseUrlProvider`.

Grade:
- Status: Partial
- Precision: Medium
- Hallucination risk: Medium (not fabricated code, but noisy ranking)
- Speed vs CLI: Faster for discovery, but requires follow-up filtering/verification

---

## Scorecard
| Module | Status | Precision | Hallucination Risk | Practical Value |
|---|---|---|---|---|
| `get_stats` | Pass | High | Low | High |
| `find_definition` | Pass | High | Low | High |
| `find_references` | Partial | Medium-High | Medium | High (Dart), Medium (Python DI) |
| `search_code` | Partial | Medium | Medium | Medium-High |

---

## Final Opinion
`code-intel` is production-useful as a primary navigation layer, especially for Dart/Flutter symbol traversal and architecture pulse checks. For Python dependency-injection patterns and concept-level retrieval, it should be paired with targeted `grep_search` before decisions or edits.

## Integration Recommendation
Adopt a two-step standard:
- Step 1: `code-intel` for candidate locations (`find_definition`, `find_references`, `search_code`).
- Step 2: `grep_search` confirmation in narrowed paths (`selos_api/app/**`, `selos_app/lib/**`) before implementation.

---

## Query Cookbook

### A) Definition Jump (Most Reliable)
Use when you already know a symbol name.

Template:
- `find_definition` symbol: `<SymbolName>`
- anchor file: where it is used

Examples:
- `ApiService` from `selos_app/lib/core/providers/api_providers.dart`
- `verify_firebase_token` from `selos_api/app/routers/analysis.py`

Validation fallback:
- `grep_search` for `class <SymbolName>|def <SymbolName>` in narrowed paths.

### B) Reference Tracing (Good, But Validate Python DI)
Use when assessing impact before edits/refactors.

Template:
- `find_references` symbol: `<SymbolName>`

Examples:
- `LoginScreen` for UI routing impact.
- `verify_firebase_token` for auth dependency impact.

Validation fallback:
- For Flutter: usually direct trust is fine.
- For FastAPI DI: run `grep_search` for `Depends(<symbol>)|from ... import <symbol>` in `selos_api/app/**`.

### C) Semantic Discovery (Use Focused Queries)
Use when you do not know exact symbol names.

High-performing query style:
- Include framework + artifact + intent.
- Keep query concrete (8-14 words).

Good examples:
- `FastAPI middleware verify firebase token bearer`
- `Riverpod provider ApiService base url`
- `analyze endpoint depends verify_firebase_token`

Weak pattern to avoid:
- Broad product-language prompts like `backend auth security architecture`.

Validation fallback:
- If top results include docs noise, immediately re-run with tighter terms and restrict follow-up grep to:
	- `selos_api/app/**`
	- `selos_app/lib/**`

### D) Fast Path Workflow (Recommended)
1. Run `search_code` or `find_references` for candidate files.
2. Confirm with `grep_search` in narrowed source paths.
3. Open/edit only after at least one exact-match confirmation.

### E) Confidence Heuristic
- High confidence tags + source file hit: usually safe to proceed.
- Low confidence/name-match only: always verify with grep before edits.
