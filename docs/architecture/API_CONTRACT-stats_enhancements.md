# Implementation Plan: get_stats Enhancements

This plan details the addition of indexing metadata persistence, expanded git summaries, and architectural rule validation (200/50 rule) to the `get_stats` tool.

## Phase 1: Foundation & Metadata
- [Architect] Define metadata schema in `src/storage.py`.
- [Architect] Implement `project_metadata` table management in `VectorStore`.
- [SeniorDev] Update `refresh_index_impl` in `src/indexer.py` to persist scan stats (time, type, model) upon completion.

## Phase 2: Git & Architectural Insights
- [SeniorDev] Implement `get_git_summary` in `src/git_utils.py` to fetch latest commit hash, message, and dirty status.
- [SeniorDev] Update `get_detailed_stats` in `src/storage.py` to calculate Rule 200/50 violations (Files > 200 lines).
- [Dev] Implementation of "Codebase Freshness" spot-check logic.

## Phase 3: Presentation & Validation
- [SeniorDev] Update `get_stats_impl` in `src/tools/stats.py` to aggregate and format all new data into the final report.
- [Dev] Add unit tests for metadata persistence and git summary parsing.
- [Dev] Verify 80% test coverage for new logic.

## Effort & Risks

### Effort Estimate
- **Total**: ~4-6 hours of development and testing.
- **Breakdown**:
    - Metadata Storage: 1hr
    - Git & Rule Logic: 2hrs
    - Integration & Formatting: 1hr
    - Testing & Coverage: 2hrs

### Risks
- **[Low] Performance**: Adding git subprocesses to `get_stats` could slow down the tool. We will use a tight timeout (2s) and parallel execution to mitigate this.
- **[Low] Schema Migration**: Adding a new table to LanceDB is safe, but we must ensure `get_stats` handles cases where legacy indexes lack the metadata table.
- **[Very Low] Git Context**: In CI environments or environments without Git, the tool must gracefully fallback to "unknown" without crashing.

## Verification Plan

### Automated Tests
- `pytest tests/test_storage.py`: Verify metadata CRUD operations.
- `pytest tests/test_git_utils.py`: Mock git output and verify summary parsing.
- `pytest tests/test_stats.py`: End-to-end check of the new report format.

### Manual Verification
- Run `refresh_index` on the `code-intel` repo.
- Run `get_stats` and verify the new sections: `Last Indexed`, `Git Summary`, and `Rule Violations`.
