# Project Progress

## Current Focus

- **Primary:** Close the remaining [`Milestone 7`](docs/PROJECT_PLAN.md) cleanup gate now that the highest-risk ranking and Python reference recall issues have been fixed.
- **Secondary:** Triage warning cleanup (`table_names()` deprecations and async runtime warnings) before benchmark packaging work in [`Milestone 8`](docs/PROJECT_PLAN.md).
- **Validation Baseline:** Latest full-suite result is `126` passing tests. Latest measured coverage baseline remains `83%` total coverage.

## Latest External Evaluation

- **Source:** [`docs/reports/code_review/code-intel-evaluation-report-2026-03-09.md`](docs/reports/code_review/code-intel-evaluation-report-2026-03-09.md)
- **Current verdict:** all five evaluated modules now grade as `Pass` after the retest.
- **Confirmed strengths:** `get_stats` remains strong and stable; `find_definition` is reliable for specific symbols; Dart and Python `find_references` are now both practically useful; `search_code` ranks the correct targets first in the benchmark queries.
- **Key validation signal:** Python chunks increased to `95`, showing the index is now capturing finer-grained Python structure such as imports and assignments.
- **Remaining nuance:** the evaluator still flags dynamic Python dictionary-key cases and Medium confidence for `Depends()` as low-priority follow-up work, not blockers.
- **Planning impact:** Milestone 7 is now in cleanup/quality-hardening mode rather than correctness-recovery mode.

## Milestone Status Overview

### Milestone 1: Core AST Indexing
- **Status:** Completed
- **Summary:** Tree-sitter integration, semantic chunking, and baseline multi-language indexing are complete.

### Milestone 2: High-Fidelity Metadata & Stability
- **Status:** Completed
- **Summary:** Complexity scoring, dependency extraction, git metadata, project pulse insights, isolation, and search metadata exposure are complete.

### Milestone 3: Advanced Intelligence (Cross-File & Graph)
- **Status:** Mostly completed, with remaining Phase 3.6 backlog
- **Completed:**
  - Phase 3.1 import resolution
  - Phase 3.2 usage/reference analysis
  - Phase 3.3 knowledge-graph persistence
  - Phase 3.4 trace tooling (`find_definition`, `find_references`)
  - Phase 3.4.6 global symbol excellence
  - Phase 3.5 domain-specific intelligence
- **Remaining:**
  - Phase 3.6 advanced linking & discovery
  - broader LLM provider integrations
  - real-time indexing on file change

### Milestone 4: Deployment & DX
- **Status:** Mostly completed
- **Completed:**
  - verification on fresh install
  - scope tuning via `include` / `exclude`
  - Windows/Jina infrastructure alignment
  - security hardening
  - professional standards / community files
  - release automation
- **Remaining:**
  - one-click installers/packages
  - comprehensive CLI dashboard
  - structural impact analysis
  - deeper DI framework support

### Milestone 5: Code Quality & Refactoring
- **Status:** In progress
- **Completed:**
  - Wave 1 quick wins
  - Wave 2 structural decomposition
  - Wave 3 performance/core refactor
  - Wave 4 production-grade scaling
  - Wave 5 secondary remediation
- **Remaining:**
  - Wave 6 enhanced agent observability follow-through in code/documentation alignment

### Milestone 6: Agent Navigation & Health
- **Status:** Completed
- **Completed:**
  - index intelligence metadata
  - git activity insight in `get_stats`
  - architectural guardian / 200-50 rule checks

### Milestone 7: Retrieval Precision & Agent Trust
- **Status:** Partially completed; highest-risk correctness issues are fixed and the cleanup gate remains
- **Completed this session:**
  - source-first retrieval bias for implementation/framework-oriented queries
  - query-intent classification
  - result-type metadata (`source`, `test`, `docs`, `report`)
  - richer reference output with confidence labels and reference-kind reporting
  - improved Python `Depends` context detection
  - regression coverage for search ranking and reference output
  - MCP re-index and live tool validation after restart
  - semantic search reranking fix so generated artifacts and raw complexity bias no longer bury relevant source candidates
  - generated-artifact demotion coverage for `GeneratedPluginRegistrant`-style files
  - Python import reference indexing via `import_from_statement` chunks
  - Python override-registration recall for `dependency_overrides[...]` patterns
  - new reference kinds surfaced for Python `import` and `override_registration`
  - full regression validation at `126` passing tests
- **Externally validated this session:**
  - Dart `find_references` improvements are holding up in real evaluation runs
  - `get_stats` remains stable and high value for first-pass orientation
  - external retest now grades all evaluated tool modules as `Pass`
- **Still remaining:**
  - fuller graph edge-kind classification
  - optional source-biased retrieval mode
  - scoped search guidance examples

#### Milestone 7 Cleanup Gate Before Milestone 8
- [x] Fix the semantic search ranking regression: preserve semantic relevance as the primary signal and prevent generated artifacts from floating to the top via metadata bias.
- [x] Add generated-artifact exclusion coverage and guidance for paths such as `**/GeneratedPluginRegistrant.*`, `**/generated/**`, and `**/build/**`.
- [x] Improve Python reference extraction/linking for import sites and common test override patterns before recalibrating confidence labels.
- [ ] Tighten heuristic confidence normalization so `name_match` stays Low unless resolution quality is stronger.
- [ ] Add regression coverage for documentation-intent ranking behavior.
- [ ] Add regression coverage for framework-shaped heuristic `name_match` confidence behavior.
- [x] Align validation artifacts to the current measured baseline (`126` tests passed; latest measured coverage remains `83%`).
- [ ] Clarify user-facing wording so source-first is described as a ranking bias rather than a retrieval guarantee.
- [ ] Triage current warnings (`table_names()` deprecations and async warning paths) before Milestone 8 begins.

### Milestone 8: Benchmarking & Decision Support
- **Status:** Not started
- **Blocked by:** completion of the remaining Milestone 7 cleanup gate items.

### Milestone 9: Agent Workflow Enablement
- **Status:** Not started
- **Dependency:** benchmark and confidence semantics should stabilize first.

## Recommended Execution Order

1. **Milestone 7:** close the remaining cleanup gate items around confidence normalization, documentation-intent coverage, wording, and warnings.
2. **Milestone 8:** formalize the now-passing external evaluation findings into repeatable retrieval benchmarks and decision signals.
3. **Milestone 9:** publish workflow guidance only after the benchmark-backed behavior and confidence semantics stabilize.
4. **Milestone 4 / 3 backlog / 5 Wave 6:** resume lower-leverage unfinished work such as one-click packaging, structural impact analysis, advanced linking backlog, real-time indexing, broader provider integrations, and observability follow-through once retrieval trust issues are addressed.

## Session Highlights

- Added and shipped the first implementation slice for [`Milestone 7`](docs/PROJECT_PLAN.md).
- Added planning/contract updates for retrieval precision work.
- Added a security reasoning report in [`docs/reports/security/SECURITY_REPORT-20260309.md`](docs/reports/security/SECURITY_REPORT-20260309.md).
- Reviewed the external evaluation in [`docs/reports/code_review/code-intel-evaluation-report-2026-03-09.md`](docs/reports/code_review/code-intel-evaluation-report-2026-03-09.md) and updated project priorities from its findings.
- Implemented the Milestone 7 semantic search reranking fix and Python reference-recall fix.
- Expanded parser/linker coverage for Python import and override-registration reference paths.
- Captured the updated external retest showing all evaluated tool modules now pass.
- Validated the MCP server after restart with:
  - full rebuild
  - `search_code`
  - `find_definition`
  - `find_references`
  - `get_stats`
- Re-ran the full repository test suite successfully with `126` passing tests.

## Verification Status

- [x] Full test suite passing (`126` tests).
- [x] Coverage remains above the project gate at the latest measured baseline of `83%` total coverage.
- [x] MCP live validation completed after a full re-index.
- [x] Milestone 7 implementation is working in the running server.
- [ ] Milestone 7 cleanup gate completed.

## Next Decision Point

Do not begin [`Milestone 8`](docs/PROJECT_PLAN.md) until the remaining [`Milestone 7`](docs/PROJECT_PLAN.md) cleanup-gate items are closed: confidence normalization hardening, documentation-intent regression coverage, wording cleanup, and warning triage.
