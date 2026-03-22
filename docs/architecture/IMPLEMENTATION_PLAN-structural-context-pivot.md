# Implementation Plan: Structural Context Reboot

## Phase 1: Foundation
- [Architect] Update `docs/architecture/API_CONTRACT-core.md` to define the rebooted tool surface around agent jobs, including `refresh_index`, `get_index_status`, `inspect_symbol`, `impact_analysis`, and `enrich_analysis`.
- [Architect] Create `docs/architecture/REBOOT_ARCHITECTURE.md` to capture preferred storage authority, dependency boundaries, reuse strategy, and phased technical direction.
- [Architect] Create `docs/architecture/API_CONTRACT-structural_core.md` to define the minimum SQLite schema and internal interfaces for the parallel structural core rebuild.
- [Architect] Update `docs/PROJECT_PLAN.md` with a dedicated pivot milestone, branch success criteria, and a stop-or-continue decision gate.
- [Architect] Update `docs/PROGRESS.md` so current work reflects the structural pivot rather than retrieval cleanup as the primary program.
- [Architect] Decide which existing tools stay primary, which become secondary, and which remain compatibility wrappers during the reboot.
- [SeniorDev] Establish a benchmark protocol using `selos` and one smaller fixture repository so refresh cost and trust regressions can be measured before and after each phase.
- [Dev] Add failing regression coverage for rename, move, delete, and chunk-id drift scenarios that currently require a full rebuild to recover correct references.

## Phase 2: Graph Freshness And Correctness
- [Architect] Define project-scoped graph ownership and invalidation rules for changed, moved, and removed files.
- [SeniorDev] Refactor graph storage and refresh orchestration so incremental refresh removes stale project-owned edges before relinking changed files.
- [SeniorDev] Ensure full rebuild and incremental refresh converge to the same final graph state for the same repository contents.
- [Dev] Add regression tests covering rename chains, deleted files, moved files, and symbol splits.

## Phase 3: Cheap Incremental Refresh
- [Architect] Define a manifest-based or diff-aware change detector that prefers file metadata and git-aware shortcuts over rehashing every candidate file.
- [Architect] Confirm the storage split: SQLite for structural authority, LanceDB only for optional semantic retrieval and enrichment.
- [SeniorDev] Implement manifest-backed incremental detection with explicit handling for removed files.
- [SeniorDev] Preserve include and exclude semantics while making unchanged refreshes materially cheaper on large repositories.
- [Dev] Add tests for unchanged runs, one-file edits, multi-file edits, removed files, and filtered refresh scenarios.

## Phase 4: Parallel Structural Core Foundation
- [Architect] Define the minimum new module set under `src/structural_core/` and the boundary between the new core and legacy compatibility code.
- [Architect] Lock the minimum SQLite schema: files, manifest, symbols, imports, edges, and refresh runs.
- [SeniorDev] Build the new structural store and manifest planner without depending on LanceDB for structural refresh decisions.
- [SeniorDev] Rebuild exact structural linking against the new SQLite authority using only exact symbol and import resolution.
- [Dev] Add bootstrap tests for schema creation, manifest diffs, exact symbol persistence, and edge persistence.

## Phase 5: Structural-Only Cutover
- [Architect] Lock the branch cutover so the default runtime abandons the legacy semantic/vector/graph core.
- [SeniorDev] Move default refresh orchestration onto the new structural core with no Ollama, LanceDB, or knowledge-graph work in the hot path.
- [SeniorDev] Port `get_stats` onto structural-core facts only.
- [Dev] Add regression coverage proving the new refresh path preserves include and exclude semantics and file removal handling.
- [Dev] Update public-tool tests so disabled legacy wrappers fail clearly instead of silently using the old runtime.

## Phase 6: Agent-Facing Tooling Rebuild
- [Architect] Finalize the `inspect_symbol` and `impact_analysis` contracts with explicit inputs, outputs, confidence semantics, and evidence fields.
- [Architect] Finalize the `get_index_status` contract for structural freshness, capability state, and trust limitations.
- [Architect] Narrow the immediate reboot goal so `get_stats` becomes the primary hotspot tool for large files, large symbols, import hubs, threshold violations, and test gaps.
- [SeniorDev] Implement `inspect_symbol` directly on structural-core facts.
- [SeniorDev] Implement `get_index_status` directly on structural-core refresh and capability state.
- [SeniorDev] Implement `impact_analysis` on structural-core edges and imports.
- [SeniorDev] Reduce refresh hot-path overhead in path normalization, symbol lookup, and import resolution before widening any richer analysis scope.
- [SeniorDev] Expand `get_stats` to report hotspot metrics and simple refactor-candidate ranking from cheap structural facts.
- [SeniorDev] Keep output explainable by attaching reasons and evidence for every affected file, symbol, or test candidate.
- [Dev] Add end-to-end tests and benchmark scenarios showing the new tools provide better first-pass guidance than raw search alone.

## Phase 6A: Trust And Scope Tightening
- [Architect] Lock the next accepted scope to four trust-first items: language-aware candidate-test filtering, structural-first test ranking, `get_stats` scope controls, and a tiny Selos regression slice.
- [Architect] Explicitly defer broad framework-aware inference, confidence-heavy explanation systems, and any richer enrichment that would expand the refresh hot path.
- [Architect] Narrow Python impact improvements to explicit import-to-call propagation, simple provider or factory edges, and only syntactically direct `Depends(...)` handling where it remains cheap and exact enough.
- [SeniorDev] Constrain candidate-test suggestions by language and nearest source root before any looser filename heuristics are considered.
- [SeniorDev] Re-rank candidate tests so structural evidence wins before folder proximity or filename similarity.
- [SeniorDev] Add `get_stats` scope controls for `code`, `tests`, and `all`, plus optional include or exclude globs and root filters.
- [SeniorDev] Improve Python downstream edges only for bounded structural patterns that do not require broad framework inference.
- [Dev] Add a tiny Selos regression slice covering `GradientScaffold`, `NotesRepository`, `activeVisualThemeIdProvider`, and `verify_firebase_token`.

## Accepted Scope For The Next Slice
- [Architect] Keep `refresh_index` cheap and unchanged in principle; no new default-path semantic or framework-aware work.
- [Architect] Improve trust and actionability in `impact_analysis` through language-aware filtering and structural-first ranking.
- [Architect] Improve `get_stats` through source and test scoping rather than more global ranking logic.
- [SeniorDev] Limit Python edge improvements to narrow explicit patterns that can stay on the structural side of the reboot thesis.

## Explicitly Deferred Scope
- [Architect] Defer broad FastAPI dependency-injection inference beyond direct obvious forms.
- [Architect] Defer framework-aware graph semantics that require custom confidence systems.
- [Architect] Defer anything that materially increases refresh cost or adds whole-repository expensive analysis.
- [Architect] Defer any attempt to make the tool generally "smart" again before the stats-first trust fixes prove themselves.

## Phase 7: Optional Rich Enrichment
- [Architect] Revisit whether `enrich_analysis` is still worth building after the structural-only core proves itself.
- [SeniorDev] Implement scoped enrichment only if the structural core has already passed the reboot decision gate.
- [Dev] Add regression coverage proving deep framework analysis remains opt-in and outside the default structural refresh path.

## Phase 8: Validation And Decision
- [SeniorDev] Re-run benchmarks on `selos` and compare full refresh, partial refresh, and trust-recovery behavior against baseline.
- [SeniorDev] Verify whether the narrowed stats-first path can hold full refresh below the 30 second target on medium repositories.
- [SeniorDev] Perform an explicit security reasoning pass over the new invalidation, manifest, storage-split, and impact-analysis logic before merge consideration.
- [Architect] Summarize the branch outcome as one of: continue investment, keep as a narrow internal tool, or stop the pivot.
- [Dev] If the branch passes the decision gate, align `README.md`, `docs/PROJECT_PLAN.md`, and `docs/PROGRESS.md` with the benchmark-backed positioning.