# Reboot Progress

## Branch

- branch: `feature/structural-context-pivot`
- mode: reboot
- objective: determine whether `code-intel` should continue as a structural context service for agents

## Current Stage

We are in reboot alignment.

The project has not yet earned the new direction. The branch currently contains planning, contract, and documentation reset work so implementation can proceed against a clean baseline.

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
- **Status:** Not started

### Milestone R2: Cheap Incremental Refresh
- **Status:** Not started

### Milestone R3: Structural-First Indexing
- **Status:** Not started

### Milestone R4: Agent-Facing Tooling
- **Status:** Not started

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

Interpretation:

- no-change refresh is not cheap enough yet, but it is dramatically better than the changed-file case
- one-file refresh is also much cheaper than the multi-file stale-file case
- the multi-file changed-state path is the more urgent performance and trust target

## Immediate Next Steps

- [ ] capture additional `selos` baseline timings for framework-heavy and full-rebuild cases
- [ ] add failing stale-graph regression tests
- [ ] start graph invalidation work

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
