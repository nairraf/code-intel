# Mission Plan: Middleware Reference Resolution

## 1. Role Assignment
**Acting Role:** Architect
**Next Pause Point:** Awaiting user sign-off on tracking strategy vs help text update.

## 2. The Contract
No external schemas or APIs are changing.
Internal Contract: Tree-sitter query mappings in `src/parser.py` must support:
*   **Python:** Decorators (`@decorator`) and functional arguments/dependency injection (`Depends(func)`).
*   **Dart:** Refine broad `(identifier)` capture to specific call/reference expressions to reduce noise and latency.

## 3. Verification Section
*   **Unit Tests:** Add tests to `tests/test_parser_usages.py` representing:
    *   Python: `@verify_token` extraction.
    *   Python: `Depends(verify_id_token)` extraction.
    *   Ensure existing usages tests still pass (`pytest tests/test_parser_usages.py`).
*   **Coverage:** Generate a coverage report (`pytest --cov=src.parser`) ensuring \> 80% coverage on `parser.py` modifications.

## 4. Execution Steps
1.  **[SENIOR]** Modify `CodeParser._extract_usages` in `src/parser.py` to include specific Tree-sitter AST queries for Python decorators and arguments.
2.  **[SENIOR]** Refine Dart queries in `_extract_usages` to remove generic `(identifier)` noise.
3.  **[DEV]** Update `tests/test_parser_usages.py` with the new edge cases.
4.  **[DEV]** Run full test suite and verify coverage.
5.  **[ARCHITECT]** Optionally update the `find_references` help text in `src/server.py` to reflect the enhanced capability.

## 5. Definition of Done
*   [x] Python decorators and argument references are reliably extracted as `SymbolUsage`.
*   [x] Dart captures are targeted, dropping false-positive `(identifier)` noise.
*   [x] `tests/test_parser_usages.py` passes.
*   [x] Coverage > 80% maintained. (Current coverage for src/parser.py: 80%)
