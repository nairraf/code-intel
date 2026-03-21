# Project Plan: Structural Context Reboot

## Overview

This branch treats `code-intel` as a rebooted project.

The old direction centered on broad semantic retrieval and incremental feature expansion. The reboot direction is narrower and stricter: prove that `code-intel` can become a fast, trustworthy structural context service for coding agents.

This document intentionally tracks only the reboot roadmap.

## Product Thesis

Agents already have strong direct navigation tools such as file search, targeted reads, and language-server assistance.

`code-intel` is only worth continuing if it can do something meaningfully better than those fallbacks for a narrow set of high-value tasks:

- identify risky refactor zones quickly
- expose dependency hubs and high-risk symbols
- maintain useful cross-file structural context
- estimate blast radius after changes
- narrow likely test impact

## Reboot Principles

1. Structural correctness is more important than semantic richness.
2. Incremental refresh must be cheap enough to run often.
3. Graph state must stay trustworthy during common refactors.
4. Embeddings are enrichment, not the foundation of correctness.
5. The branch succeeds only if benchmarked agent usefulness improves.
6. When the legacy path fights the reboot thesis, rebuild the hot path instead of continuing in-place reduction.

## Branch Scope

- Branch of record: `feature/structural-context-pivot`
- Mode: time-boxed rescue attempt
- Main question: should this project continue under the new structural-context thesis?

## Reboot Success Criteria

The reboot is considered successful only if all of the following become true:

1. partial refresh on large repositories is materially faster than the current behavior
2. incremental refresh no longer leaves obviously stale graph state after rename, move, and delete workflows
3. structural tools remain usable when embeddings are delayed or unavailable
4. impact analysis provides first-pass value beyond raw search alone
5. the touched code remains above the repository quality gate

## Latest External Evidence

The branch now has initial external validation on `selos`.

- a full structural rebuild completed in about `29.49s` across `203` files
- trust reporting returned usable current-state output after rebuild
- the structural-only toolset produced meaningful symbol and impact results for Dart, Python, and Firestore
- the main remaining quality gaps were heuristic-heavy test ranking and limited richer framework-depth for Dart or Flutter workflows

This is enough evidence to keep the reboot alive. It is not yet enough evidence to declare the reboot complete.

## Architecture Baseline

The reboot keeps these core assets:

- Tree-sitter-based parsing
- chunked structural representation
- graph-backed cross-file relationships
- MCP delivery model
- existing health and stats concepts

The reboot changes the execution model:

- structural indexing becomes the authoritative path
- embeddings become optional enrichment
- impact analysis becomes a first-class workflow

The preferred architecture and technology direction are documented in `docs/architecture/REBOOT_ARCHITECTURE.md`.

## Reboot Milestones

### Milestone R0: Reboot Alignment
- **Status:** In progress
- **Goal:** reset docs, branch narrative, contracts, and implementation planning around the new direction.
- **Deliverables:**
	- [x] reboot branch created
	- [x] core contract rewritten for structural-first behavior
	- [x] reboot implementation plan created
	- [x] README, project plan, and progress reset around the reboot
	- [x] reboot tool surface locked with keep, add, and compatibility decisions
	- [x] preferred architecture and technology direction documented
	- [x] reboot benchmark protocol captured

### Milestone R1: Graph Freshness
- **Status:** In progress
- **Goal:** make incremental graph state trustworthy.
- **Deliverables:**
	- [x] project-scoped graph ownership
	- [x] stale edge invalidation for changed files
	- [x] removal handling for deleted and moved files
	- [x] regression tests for rename, move, delete, and symbol split cases
	- [ ] benchmark validation on `selos`
	- [ ] wider multi-file refactor validation

### Milestone R2: Cheap Incremental Refresh
- **Status:** In progress
- **Goal:** remove the current whole-tree cost profile from partial refresh.
- **Deliverables:**
	- [x] manifest-based change detection using file metadata before hashing
	- [x] unchanged refresh path that avoids rehashing every candidate file
	- [ ] filtered refresh behavior preserved
	- [ ] benchmark comparison on `selos`
	- [ ] further reduction of fixed incremental overhead beyond hashing

### Milestone R2.5: Parallel Structural Core Rebuild
- **Status:** Completed
- **Goal:** replace the legacy refresh engine as the primary implementation path with a smaller structural core built for the reboot thesis.
- **Deliverables:**
	- [x] minimum SQLite schema defined for files, manifest, symbols, imports, edges, and refresh runs
	- [x] new `src/structural_core/` package scaffolded
	- [x] exact symbol and import persistence built against the new store
	- [x] `refresh_index` cutover approved as structural-only by default
	- [x] default refresh execution ported onto the new core with no legacy runtime work in the hot path
	- [x] structural `get_stats` ported onto the new core
	- [x] exact structural linking built without LanceDB as the structural authority

### Milestone R3: Structural-First Indexing
- **Status:** Completed
- **Goal:** finish the new-core tool surface on top of the structural-only runtime.
- **Deliverables:**
	- [x] structural indexing completes without any dependency on embeddings in the default path
	- [x] `get_index_status` implemented for trust and freshness visibility
	- [x] `inspect_symbol` implemented on the structural core
	- [x] regression coverage for structural-only operation

### Milestone R4: Agent-Facing Tooling
- **Status:** In progress
- **Goal:** add the first reboot-native agent tools with clear value.
- **Deliverables:**
	- [x] `inspect_symbol` contract and implementation
	- [x] `impact_analysis` contract finalized
	- [x] `impact_analysis` implementation
	- [x] explainable output with reasons and confidence labels
	- [x] test impact candidates included in the analysis output
	- [x] `get_index_status` implemented and exposed on the structural core
	- [x] live MCP validation completed on this repository
	- [x] initial usefulness benchmark completed on `selos`
	- [ ] broader real-agent workflow validation and quality follow-through

### Milestone R5: Scoped Rich Enrichment
- **Status:** Not started
- **Goal:** revisit optional enrichment only after the structural-only core proves its value.
- **Deliverables:**
	- [ ] `enrich_analysis` contract and implementation
	- [ ] analyzer taxonomy for decorators, middleware, dependency injection, route registration, and test impact
	- [ ] path-centered and neighborhood-aware enrichment behavior
	- [ ] proof that rich analysis is optional and does not block structural correctness

### Milestone R6: Go Or No-Go Validation
- **Status:** Not started
- **Goal:** decide whether the reboot direction deserves continued investment.
- **Deliverables:**
	- [ ] before and after benchmark comparison
	- [ ] trust evaluation on real refactor workflows
	- [ ] security reasoning log for new logic
	- [ ] continue, narrow, or stop recommendation

## Deferred Legacy Backlog

The following legacy items remain valid only if the reboot succeeds:

- packaging and installer work
- dashboard work
- real-time indexing on file change
- additional retrieval cleanup
- broader provider integrations
- advanced linking experiments

They are intentionally not part of the reboot critical path.

## Legacy Documentation Handling

Legacy planning documents may remain in the repository for historical context, but they are no longer authoritative for this branch unless explicitly referenced by the reboot plan.

## Implementation Plan Reference

The working reboot plan is maintained in `docs/architecture/IMPLEMENTATION_PLAN-structural-context-pivot.md`.

## Execution Order

1. complete Milestone R0 baseline and benchmark setup
2. execute R1 and the smallest useful part of R2 to prove current-path assumptions
3. move immediately into R2.5 parallel structural core rebuild
4. execute R3 only after the new structural core owns refresh and stats
5. execute R4 only after structural freshness is credible on the new core
6. execute R5 only as scoped opt-in enrichment
7. use R6 to decide whether the project continues in this new form

## Benchmark Reference

The active reboot benchmark protocol is maintained in `docs/architecture/BENCHMARK_PROTOCOL-structural-context-reboot.md`.
