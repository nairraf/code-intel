# Mission Plan: Selos Report Improvements

## 1. Role Assignment
**Acting Role:** Architect
**Next Pause Point:** Awaiting Ian's sign-off on the proposed improvements based on the Selos report.

## 2. The Contract
**Documentation Updates:**
*   `find_references`: Clarify that a fresh `refresh_index` is required to track complex middleware/decorators.
*   `find_definition`: Clarify `filename` and `line` usage in the help text.
*   `search_code`: Clarify difference between 'Project Pulse' metadata (get_stats) vs file-level metadata.

**Implementation Fix:**
*   **Current State:** `find_definition` in `src/server.py` completely ignores the `filename` and `line` parameters, natively passing down only `symbol_name` to `vector_store.find_chunks_by_symbol`. This causes total failure for dependency injection (like FastAPI's `Depends()`) where the token usage might not precisely match a top-level symbol name.
*   **Target State:** Refactor `find_definition` to use the provided `filename` and `line` to resolve the *SymbolUsage* via the `parser`, and traverse the `knowledge_graph` logically back to its origin, bringing it in line with true LSP "jump to definition" behavior.

## 3. Verification Section
*   **Unit Tests:** Add/Update tests in `tests/` to verify `find_definition` correctly resolves via `filename` and `line` instead of just a raw symbol name search.
*   **Coverage:** Ensure `src/server.py` and `src/linker.py` (if modified) maintain > 80% coverage.

## 4. Execution Steps
1.  **[ARCHITECT]** Update MCP tool descriptions in `src/server.py` (Low Effort - 5 mins).
2.  **[SENIOR]** Overhaul `_find_definition` in `src/server.py` to utilize `filename` and `line` for AST-based origin resolution (Medium Effort - 1-2 hours).
3.  **[DEV]** Update unit tests to cover the new `find_definition` pathing.
4.  **[DEV]** Run `pytest --cov` to ensure the Hard Gate (80% coverage) is met.

## 5. Definition of Done
*   [x] Tool documentation updated per Selos report recommendations.
*   [x] `find_definition` successfully resolves origin via `filename` and `line`.
*   [x] Tests pass and coverage is >= 80%.
