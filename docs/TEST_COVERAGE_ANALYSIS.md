# Test Coverage Analysis & Recommendations

## 1. Summary of Findings
Based on `code-intel get-stats` and a manual review of the `tests/` directory, the codebase has a reasonable foundation of unit tests but significant gaps in **integration testing** and **core storage logic details**.

- **Current State**: Unit tests exist for most components (`OllamaClient`, `CodeParser`, `ImportResolver`), but they rely heavily on mocks.
- **Critical Risk**: The `VectorStore` class, which handles the actual database interactions (LanceDB), has very little direct testing. `get_detailed_stats` logic is entirely unverified by tests.
- **Coverage Stats**:
  - `VectorStore`: **Low** (35 chunk gap)
  - `JSImportResolver`: **Medium** (32 chunk gap - mostly edge cases)
  - `PythonImportResolver`: **Medium** (21 chunk gap)
  - `get_detailed_stats`: **Zero** (18 chunk gap - mocked in tests)
  - `refresh_index_impl`: **Medium** (17 chunk gap - integration logic mocked)

## 2. Identified Gaps

### A. VectorStore & LanceDB Integration
- **Gap**: `src.storage.VectorStore` methods like `get_detailed_stats`, `delete_project`, and edge cases in `upsert_chunks` are not tested with a real instance.
- **Risk**: Changes to LanceDB schema or query logic might break the application without tests failing, as tests currently mock these calls.
- **Evidence**: `test_get_stats.py` mocks `vector_store.get_detailed_stats` entirely. `test_system.py` mocks `vector_store` for search and stats. `test_isolation.py` is the only test using a real DB, but covers only basic upsert/search.

### B. Full System Integration
- **Gap**: There is no "End-to-End" test that runs `refresh_index` -> `parse` -> `embed` -> `upsert` -> `search` without mocks.
- **Risk**: Wiring issues between components (e.g., parser output format vs. embedder input expectation) might be missed.

### C. Import Resolution Edge Cases
- **Gap**: While `test_resolution_*.py` exist, the stats indicate significant uncovered chunks in `javascript.py` and `python.py`. This likely corresponds to error handling (`try/except` blocks), complex alias resolution, or specific node types not encountered in current test cases.

## 3. Recommendations

### Immediate Actions (High Priority)
1.  **[DONE] Create `test_storage.py`**:
    -   Instantiate a real `VectorStore` with a temp directory.
    -   Test `upsert_chunks`, `search` (with dummy vectors), `get_detailed_stats`, `delete_project`.
    -   **Result**: `VectorStore` gaps closed in `get_stats`.

2.  **[DONE] Create `test_integration_full.py`**:
    -   Create a small temp file structure.
    -   Run `refresh_index.fn` (mocking *only* `OllamaClient` to avoid API costs/latency, but using real Parser and VectorStore).
    -   Verify data persists to disk and `search_code.fn` retrieves it.

3.  **Enhance `test_resolution_*.py`**:
    -   Add test cases for invalid imports, missing files, and deeply nested structures to hit the uncovered lines.

### Strategic Updates to Project Plan
-   Add a **"Hardened Testing"** phase to `Milestone 4`.
-   Require **"Real DB Tests"** for any changes to `storage.py`.

## 4. Conclusion
The current test suite is good for logic verification (parsers, resolvers) but creates a false sense of security regarding data persistence and retrieval due to excessive mocking of the `VectorStore`. Filling the `VectorStore` testing gap is the highest priority.
