# Reboot Progress

## Branch

- branch: `feature/structural-context-pivot`
- mode: reboot
- objective: determine whether `code-intel` should continue as a structural context service for agents

## Current Stage

We are in external validation and reboot decision shaping.

The branch now has a structural-only default runtime plus the first reboot-native trust and analysis tools running live on the new core. Initial validation on `selos` now says the core is practical enough to keep evaluating. The next question is narrower: whether the reboot earns continued investment after follow-through on ranking quality, trust messaging, and broader real-agent usefulness.

## What Has Been Reset

- README rewritten around the reboot thesis
- project roadmap rewritten around reboot milestones
- progress tracking reset to reboot status only
- implementation plan established for the structural pivot
- reboot tool surface locked around primary, secondary, and compatibility tools
- preferred reboot architecture and technology direction documented

## Current Working Assumption

The old retrieval-centric direction is no longer the main decision axis.

The branch will be judged on whether it improves these practical outcomes:

1. refresh cost during active work
2. trustworthiness of graph state during refactors
3. usefulness of structural insight for agent decisions

## Reboot Status By Milestone

### Milestone R0: Reboot Alignment
- **Status:** In progress
- **Completed:**
  - [x] feature branch created
  - [x] reboot docs baseline created
  - [x] reboot contract defined
  - [x] reboot implementation plan written
  - [x] reboot tool surface locked
  - [x] reboot architecture direction documented
  - [x] reboot benchmark protocol captured
- **Remaining:**
  - [ ] baseline measurements captured

### Milestone R1: Graph Freshness
- **Status:** In progress
- **Completed:**
  - [x] project-scoped graph ownership added to stored edges
  - [x] stale edge invalidation for changed files added
  - [x] removal handling for deleted and moved files added
  - [x] regression tests added for rename, move, delete, and chunk-id drift scenarios
- **Remaining:**
  - [ ] benchmark the new behavior on `selos`
  - [ ] validate convergence further against larger multi-file refactors

### Milestone R2: Cheap Incremental Refresh
- **Status:** In progress
- **Completed:**
  - [x] manifest-based file-state persistence added
  - [x] unchanged refresh path now uses `mtime_ns` and `size` before falling back to hashing
  - [x] regression tests added proving unchanged incrementals skip whole-file rehashing
  - [x] regression tests added proving one-file edits hash only changed files in the focused fixture
- **Remaining:**
  - [ ] preserve and validate filtered refresh behavior explicitly
  - [ ] benchmark the new fast path on `selos`
  - [ ] reduce additional fixed overhead beyond file hashing

### Milestone R2.5: Parallel Structural Core Rebuild
- **Status:** Completed
- **Completed:**
  - [x] branch direction reset toward a minimal parallel rebuild rather than further in-place stripping
  - [x] minimum structural core schema defined
  - [x] `src/structural_core/` scaffolded
  - [x] exact symbol and import persistence added to the new core
  - [x] basic structural refresh flow added for manifest diff, exact persistence, and file removal
  - [x] structural-only cutover approved for the branch default runtime
  - [x] default refresh no longer executes legacy semantic or graph work
  - [x] `get_stats` now reads structural-core facts only
  - [x] exact structural edges now persist in SQLite and relink unchanged callers after target changes
  - [x] `inspect_symbol`, `impact_analysis`, and `get_index_status` now execute directly on the new structural core

### Milestone R3: Structural-First Indexing
- **Status:** Completed
- **Completed:**
  - [x] structural indexing now completes without any dependency on embeddings in the default path
  - [x] `get_index_status` implemented for trust and freshness visibility
  - [x] `inspect_symbol` implemented on the structural core
  - [x] regression coverage added for structural-only operation

### Milestone R4: Agent-Facing Tooling
- **Status:** In progress
- **Completed:**
  - [x] `inspect_symbol` implemented on structural-core definitions and incoming edges
  - [x] `impact_analysis` implemented on structural-core symbols, edges, and tracked-file heuristics
  - [x] explainable reasons and confidence labels returned for affected files, symbols, and candidate tests
  - [x] `get_index_status` implemented on structural-core freshness and capability state
  - [x] live MCP validation completed for `inspect_symbol`, `impact_analysis`, and `get_index_status` on this repository
  - [x] `impact_analysis` ranking tightened to reduce same-file file noise, heuristic test spillover, and changed-file symbol noise
  - [x] dirty workspaces now report usable structural freshness with explicit warnings instead of generic stale status immediately after a successful rebuild
  - [x] disabled legacy wrappers are now hidden from MCP discovery so the exposed tool catalog matches the branch reality
  - [x] initial external validation on `selos` confirmed practical rebuild speed plus useful structural output in Dart, Python, and Firestore
- **Remaining:**
  - [ ] improve broader real-agent usefulness, especially Dart or Flutter impact depth and test candidate quality

### Milestone R5: Scoped Rich Enrichment
- **Status:** Not started

### Milestone R6: Go Or No-Go Validation
- **Status:** Not started

## Baseline Facts Carried Forward

- last recorded full-suite result from the pre-reboot state: `126` tests passing
- last recorded coverage baseline from the pre-reboot state: `83%`

These numbers are useful historical context, but they are not yet reboot-branch validation for the new direction.

## Reboot Benchmark Baselines Captured So Far

- `selos` incremental refresh with changed files:
  - stale files: `84`
  - elapsed time: approximately `12 minutes`
  - assessment: unacceptable in current state
- `selos` incremental refresh with no file changes:
  - scanned files: `203`
  - skipped files: `196`
  - total chunks: `920`
  - elapsed time: approximately `1 minute`
- `selos` incremental refresh with one changed file:
  - changed file: `config.py`
  - scanned files: `203`
  - skipped files: `195`
  - total chunks: `920`
  - elapsed time: approximately `1 minute`
- `selos` structural-core reboot validation:
  - full rebuild: `203` files in approximately `29.49 seconds`
  - post-refresh trust state: `status ok`, `structuralState current`, `workspaceState clean`
  - observed useful symbol and impact output for Dart, Python, and Firestore
  - observed limitation: test candidate selection remains heuristic-heavy and deeper framework-aware impact is still deferred

Interpretation:

- no-change refresh is not cheap enough yet, but it is dramatically better than the changed-file case
- one-file refresh is also much cheaper than the multi-file stale-file case
- the multi-file changed-state path is the more urgent performance and trust target
- the reboot now has credible external evidence that the structural-only core is useful, but not yet enough evidence to declare the decision gate passed

## Immediate Next Steps

- [ ] deepen `selos` follow-up on Dart or Flutter impact depth and test candidate quality
- [ ] capture before-and-after evidence for the reboot decision gate
- [ ] write the security reasoning and trust summary for the new structural core logic

## Preferred Technical Direction

The current preferred direction is:

- SQLite-backed structural authority
- optional LanceDB-backed semantic retrieval
- explicit trust and freshness signals
- primary tools designed around agent jobs rather than internal pipeline stages

## Decision Gate

Do not treat the reboot as successful until the branch demonstrates all three:

1. materially cheaper partial refresh
2. materially more trustworthy incremental graph behavior
3. a practical impact-analysis workflow that an agent would choose to use
