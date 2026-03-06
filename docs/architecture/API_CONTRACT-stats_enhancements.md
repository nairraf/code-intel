# Implementation Plan: get_stats Enhancements

This plan details the addition of indexing metadata persistence, Git-centric codebase freshness spot-checks, expanded git summaries, and architectural rule validation (200/50 rule) to the `get_stats` tool.

## Schemas & Interfaces

### `IndexMetadata` Schema
Stored in LanceDB `project_metadata` table (or sqlite).
```python
class IndexMetadata(BaseModel):
    indexed_at: str          # ISO-8601 timestamp
    commit_hash: Optional[str] # Git commit hash at time of indexing (if available)
    is_dirty: bool           # Whether workspace had uncommitted changes during index
    scan_type: str           # e.g., "full", "incremental"
    model_name: str          # e.g., "bge-m3"
```

### `get_stats` Output Addition (`index_health` block)
Included in the final JSON response of `get_stats` MCP tool.
```json
"index_health": {
  "last_indexed_at": "2026-03-05T10:00:00Z",
  "indexed_commit": "a1b2c3d",
  "current_commit": "f89a2b",
  "is_workspace_dirty": false,
  "freshness_status": "STALE",
  "reason": "Current commit differs from indexed commit.",
  "recommendation": "Call refresh_index before relying on search_code."
}
```
*Note: `freshness_status` can be "FRESH", "STALE", "DIRTY", or "UNKNOWN" (if not a git repo).*

## Phase 1: Foundation & Metadata
- [ ] **[Architect]** Enhance `docs/architecture/API_CONTRACT-stats_enhancements.md` with Git-centric schemas.
- [ ] **[SeniorDev]** Implement `project_metadata` table management in `src/storage.py` (or existing DB layer).
- [ ] **[SeniorDev]** Update `refresh_index_impl` in `src/indexer.py` to capture current Git commit hash and dirty status, and persist into `IndexMetadata`.

## Phase 2: Git & Architectural Insights
- [ ] **[SeniorDev]** Implement fast `get_current_git_commit` and `check_git_dirty` in `src/git_utils.py` with tight timeouts (e.g., 2s) and graceful failures.
- [ ] **[SeniorDev]** Build "Codebase Freshness" spot-check logic within `get_stats` flow: compare current HEAD hash and dirty status against stored `IndexMetadata`.
- [ ] **[SeniorDev]** Update `get_detailed_stats` in `src/storage.py` to identify Rule 200/50 violations (e.g., tracking files > 200 lines).

## Phase 3: Presentation & Validation
- [ ] **[Dev]** Update `get_stats_impl` in `src/tools/stats.py` to aggregate freshness and rule violation data into the final JSON report.
- [ ] **[Dev]** Add unit tests for metadata persistence, git hash comparison, and freshness evaluation to maintain >80% coverage.
- [ ] **[Dev]** Verify graceful fallback when Git is not available or repository is not initialized.
