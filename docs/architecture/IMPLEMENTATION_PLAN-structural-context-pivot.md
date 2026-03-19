# Implementation Plan: Structural Context Reboot

## Phase 1: Foundation
- [Architect] Update `docs/architecture/API_CONTRACT-core.md` to define the rebooted tool surface around agent jobs, including `refresh_index`, `get_index_status`, `inspect_symbol`, `impact_analysis`, and `enrich_analysis`.
- [Architect] Create `docs/architecture/REBOOT_ARCHITECTURE.md` to capture preferred storage authority, dependency boundaries, reuse strategy, and phased technical direction.
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

## Phase 4: Structural-First Indexing
- [Architect] Define the lifecycle boundary between structural indexing and semantic enrichment.
- [SeniorDev] Refactor refresh so parsing, chunk persistence, and graph linking complete before embeddings are required.
- [SeniorDev] Add deferred or background embedding generation and expose enough state for callers to know whether enrichment is pending.
- [SeniorDev] Add `get_index_status` so agents can check trust, freshness, and degraded-mode signals before relying on downstream analysis.
- [Dev] Add regression coverage proving structural tools remain useful when embeddings are slow or unavailable.

## Phase 5: Agent-Facing Tooling
- [Architect] Finalize the `inspect_symbol` and `impact_analysis` contracts with explicit inputs, outputs, confidence semantics, and evidence fields.
- [SeniorDev] Implement `inspect_symbol` as the preferred agent-facing wrapper over definition and reference inspection.
- [SeniorDev] Implement `impact_analysis` using graph edges, dependencies, related-test heuristics, and chunk metadata.
- [SeniorDev] Keep output explainable by attaching reasons and evidence for every affected file, symbol, or test candidate.
- [Dev] Add end-to-end tests and benchmark scenarios showing the new tools provide better first-pass guidance than raw search alone.

## Phase 6: Scoped Rich Enrichment
- [Architect] Finalize the `enrich_analysis` contract, analyzer taxonomy, and separation between exact facts and inferred facts.
- [SeniorDev] Implement scoped enrichment for targeted analyzers such as decorators, middleware, dependency injection, route registration, and test impact.
- [SeniorDev] Keep rich analysis path-centered and neighborhood-aware instead of whole-repository by default.
- [Dev] Add regression coverage proving deep framework analysis is opt-in and does not block structural refresh.

## Phase 7: Validation And Decision
- [SeniorDev] Re-run benchmarks on `selos` and compare full refresh, partial refresh, and trust-recovery behavior against baseline.
- [SeniorDev] Perform an explicit security reasoning pass over the new invalidation, manifest, storage-split, and impact-analysis logic before merge consideration.
- [Architect] Summarize the branch outcome as one of: continue investment, keep as a narrow internal tool, or stop the pivot.
- [Dev] If the branch passes the decision gate, align `README.md`, `docs/PROJECT_PLAN.md`, and `docs/PROGRESS.md` with the benchmark-backed positioning.