# Benchmark Protocol: Structural Context Reboot

## Purpose

This document defines the benchmark protocol for the reboot branch.

The benchmark is intended to answer three questions:

1. is refresh cheap enough for frequent use during active work?
2. does incremental refresh remain trustworthy after change-heavy workflows?
3. do the reboot-native tools provide enough value to justify continued investment?

## Primary Benchmark Repository

- primary repo: `D:/Development/selos`

### Selos Context
- mixed-language repository
- Python API
- Azure IaC Bicep
- Flutter and Dart mobile app
- original text sources used to build and populate Azure Search indexes
- repository size: approximately `11.4 GB`
- storage: SSD
- git operations: reported as fast and not a bottleneck

### Environment Baseline
- CPU: Ryzen 7 3800X
- observed CPU behavior during incremental refresh: approximately `50%` to `60%` across `8` cores at around `3.9 GHz`
- GPU: Radeon `7800 XT`
- observed GPU behavior during incremental refresh: light spikes below `30%`, average around `5%`
- Ollama version: `0.18.0`
- active embedding model: `unclemusclez/jina-embeddings-v2-base-code:latest`
- model processor: `100% GPU`

## Benchmark Cases

### B1: Incremental No-Change Refresh
Purpose:
measure the cost of a trust check and unchanged refresh path.

Target:
- should feel cheap enough to run routinely
- initial target: under `10` seconds

### B2: Incremental Small Change Refresh
Purpose:
measure refresh after `1` to `3` changed files.

Target:
- initial target: under `20` to `30` seconds

### B3: Incremental Medium Refactor Refresh
Purpose:
measure refresh after `10` to `30` related file changes.

Target:
- initial target: under `60` seconds

### B4: Incremental Framework-Heavy Refresh
Purpose:
measure refresh on Python decorator, middleware, or dependency-injection heavy changes.

Target:
- structural refresh remains fast enough for iteration
- deep framework enrichment must not be required for baseline correctness

### B5: Full Rebuild
Purpose:
measure the cold recovery or first-index path.

Target:
- materially less than the currently reported `~20 minutes`

### B6: Scoped Rich Enrichment
Purpose:
measure the cost of explicit opt-in enrichment for a targeted area.

Target:
- may be slower than structural refresh
- must remain scoped
- must not block normal structural refresh

## Required Metrics Per Run

Record these fields when available:

- benchmark case id
- timestamp
- input arguments
- elapsed time
- stale file count if reported
- files scanned
- files skipped
- files changed if known
- total chunks after run
- whether embeddings were active
- whether the resulting state appeared trustworthy
- notes on CPU and GPU behavior if observed

## Baseline Measurements

### Baseline A: Incremental Refresh With Changed Files
- benchmark case: `B3` candidate baseline
- input:

```json
{ "root_path": "D:/Development/selos", "force_full_scan": false }
```

- observed stale files: `84`
- start time: `11:45`
- stop time: `11:57`
- elapsed time: approximately `12 minutes`
- observation: current incremental performance is unacceptable in present state

### Baseline B: Incremental No-Change Refresh
- benchmark case: `B1` baseline
- input:

```json
{ "root_path": "D:/Development/selos", "force_full_scan": false }
```

- start time: `12:02`
- stop time: `12:03`
- elapsed time: approximately `1 minute`
- result summary: `Incremental reindex complete: scanned 203 files (196 skipped), index now has 920 chunks.`

### Baseline C: Incremental One-File Change Refresh
- benchmark case: `B2` baseline
- input:

```json
{ "root_path": "D:/Development/selos", "force_full_scan": false }
```

- changed file: `config.py`
- change summary: `APP_NAME` set to `"Selos Intelligence API - reindex-test"`
- start time: `12:10`
- stop time: `12:11`
- elapsed time: approximately `1 minute`
- result summary: `Files Scanned: 203 (195 skipped); Total Chunks: 920.`

## Initial Interpretation

- the no-change path is far cheaper than the changed-file path
- a one-file structural change is currently close to the no-change path, which suggests the biggest failure mode is not single-file refresh overhead
- repository walk and change detection are still non-trivial costs, but not the dominant failure mode
- the most urgent reboot work should focus on multi-file changed-state invalidation, changed-file processing cost at scale, and keeping deep enrichment out of the default refresh path

## Success Criteria For Reboot Evaluation

The reboot is trending in the right direction when:

1. `B1` no-change refresh becomes consistently cheap enough to feel routine
2. `B2` stays cheap enough for routine use and `B3` becomes materially faster than the current baseline
3. `B4` does not force full rich analysis just to maintain structural correctness
4. `B5` improves meaningfully from the current `~20 minute` full rebuild baseline
5. trust after refresh improves alongside performance