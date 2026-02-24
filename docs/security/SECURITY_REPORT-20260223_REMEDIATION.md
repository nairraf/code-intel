# Remediation Plan — SECURITY_REPORT-20260223

**Source Report:** [SECURITY_REPORT-20260223.md](file:///d:/Development/code-intel/docs/security/SECURITY_REPORT-20260223.md)
**Created:** 2026-02-23
**Total Findings:** 7 (2 HIGH, 3 MEDIUM, 2 LOW)
**Estimated Total Effort:** ~2.5 hours

> [!IMPORTANT]
> Findings are ordered by priority. After each remediation, run the full test suite (`uv run pytest tests/ -v --tb=short`) to verify no regressions.

---

## Phase 1 — Critical (HIGH Severity)

### FINDING-2: Replace `pickle` with `json` in EmbeddingCache

**File:** [cache.py](file:///d:/Development/code-intel/src/cache.py)
**Risk:** Arbitrary code execution via crafted cache payload (CWE-502)
**Effort:** ~30 min

#### Steps

1. **Remove `pickle` import**, add `json` import at the top of `cache.py`:

```diff
-import pickle
+import json
```

2. **Replace serialization in `set()` method** (line 84):

```diff
-blob = pickle.dumps(vector)
+blob = json.dumps(vector).encode('utf-8')
```

3. **Replace deserialization in `get()` method** (line 74):

```diff
-return pickle.loads(row[0])
+return json.loads(row[0])
```

4. **Handle migration from legacy pickle data.** Wrap the deserialization in a try/except so old pickle-encoded entries degrade gracefully instead of crashing:

```python
try:
    return json.loads(row[0])
except (json.JSONDecodeError, TypeError):
    # Legacy pickle entry — discard it, it will be re-fetched
    logger.info(f"Evicting legacy pickle cache entry: {text_hash}")
    conn.execute("DELETE FROM embeddings WHERE hash = ?", (text_hash,))
    return None
```

5. **Verify:** Run existing cache tests. Manually confirm a cache miss → Ollama fetch → cache hit cycle works with the new JSON format.

6. **Optional cleanup:** After deploying the fix, consider running a one-time prune (`self.prune(days=0)`) to clear all legacy pickle entries. This can be a separate follow-up.

---

### FINDING-1: Parameterize LanceDB Filter Queries

**File:** [storage.py](file:///d:/Development/code-intel/src/storage.py)
**Risk:** Data corruption/deletion via filter injection (CWE-89 analog)
**Effort:** ~1 hour

#### Steps

1. **Create a sanitization helper** at the top of `storage.py`:

```python
import re

def _sanitize_filter_value(value: str) -> str:
    """
    Escapes a string value for safe inclusion in LanceDB SQL-like filters.
    Doubles internal quotes and validates against injection patterns.
    """
    if not isinstance(value, str):
        value = str(value)
    # Escape internal double quotes
    escaped = value.replace('"', '""')
    # Reject values containing SQL keywords that shouldn't appear in identifiers
    # This is defense-in-depth; the escaping above should be sufficient
    dangerous_patterns = re.compile(r'\b(OR|AND|DROP|DELETE|INSERT|UPDATE|UNION|;)\b', re.IGNORECASE)
    if dangerous_patterns.search(escaped):
        raise ValueError(f"Potentially dangerous filter value rejected: {value!r}")
    return escaped
```

2. **Apply the helper to all raw filter sites:**

   **Line 95** — `upsert_chunks` delete filter (already has basic escaping, upgrade it):
   ```diff
   -safe_path = path.replace('"', '""')
   -table.delete(f'filename = "{safe_path}"')
   +safe_path = _sanitize_filter_value(path)
   +table.delete(f'filename = "{safe_path}"')
   ```

   **Line 118** — `find_chunks_by_symbol`:
   ```diff
   -results = table.search().where(f'symbol_name = "{symbol_name}"').to_list()
   +safe_name = _sanitize_filter_value(symbol_name)
   +results = table.search().where(f'symbol_name = "{safe_name}"').to_list()
   ```

   **Lines 130-132** — `find_chunks_by_symbol_in_file`:
   ```diff
   -safe_filepath = normalize_path(filepath).replace('"', '""')
   -results = table.search().where(f'symbol_name = "{symbol_name}" AND filename = "{safe_filepath}"').to_list()
   +safe_name = _sanitize_filter_value(symbol_name)
   +safe_filepath = _sanitize_filter_value(normalize_path(filepath))
   +results = table.search().where(f'symbol_name = "{safe_name}" AND filename = "{safe_filepath}"').to_list()
   ```

   **Line 145** — `get_chunk_by_id`:
   ```diff
   -results = table.search().where(f'id = "{chunk_id}"').to_list()
   +safe_id = _sanitize_filter_value(chunk_id)
   +results = table.search().where(f'id = "{safe_id}"').to_list()
   ```

3. **Add unit tests** for `_sanitize_filter_value`:
   - Normal symbol names pass through unchanged
   - Strings with `"` are doubled
   - Strings with SQL keywords raise `ValueError`

4. **Verify:** Re-run `uv run pytest tests/ -v` — ensure all existing storage tests still pass and that search/upsert/delete workflows are functional.

---

## Phase 2 — Hardening (MEDIUM Severity)

### FINDING-4: Add Project Root Containment to Import Resolvers

**Files:**
- [python.py](file:///d:/Development/code-intel/src/resolution/python.py)
- [javascript.py](file:///d:/Development/code-intel/src/resolution/javascript.py)
- [dart.py](file:///d:/Development/code-intel/src/resolution/dart.py)

**Risk:** Path traversal outside project boundary (CWE-22)
**Effort:** ~30 min

#### Steps

1. **Add a containment check to the base class** in [base.py](file:///d:/Development/code-intel/src/resolution/base.py):

```python
@staticmethod
def _is_within_root(resolved_path: Path, project_root: Path) -> bool:
    """Ensures a resolved path stays within the project boundary."""
    try:
        resolved = Path(resolved_path).resolve()
        root = Path(project_root).resolve()
        resolved.relative_to(root)
        return True
    except ValueError:
        return False
```

2. **Apply the containment check in each resolver's `resolve()` method**, just before returning a resolved path. For example in `javascript.py`:

```diff
 def _resolve_relative(self, source_file: str, import_string: str) -> Optional[str]:
     source_dir = Path(source_file).parent
     try:
         target_path = (source_dir / import_string).resolve()
+        # Containment check omitted here — applied in resolve() caller
         if target_path.exists() and target_path.is_file():
             return str(target_path)
```

   Alternatively, wrap the return in the top-level `resolve()` method of each resolver:
   ```python
   result = self._resolve_relative(source_file, import_string)
   if result and project_root and not self._is_within_root(result, project_root):
       return None
   return result
   ```

3. **Apply the same pattern to all three resolvers** (`PythonImportResolver`, `JSImportResolver`, `DartImportResolver`).

4. **Add unit tests** that attempt `../../etc/passwd`-style traversals and verify they return `None`.

---

### FINDING-5: Migrate MD5 → SHA-256 for Identifiers

**Files:**
- [storage.py](file:///d:/Development/code-intel/src/storage.py) — `_get_table_name` (line 23)
- [parser.py](file:///d:/Development/code-intel/src/parser.py) — `_create_chunk` (line 338)

**Risk:** Hash collision leading to data corruption (CWE-328)
**Effort:** ~15 min

> [!WARNING]
> Changing the hash function will invalidate existing LanceDB tables and chunk IDs. Users will need to run a `force_full_scan=True` re-index after this change.

#### Steps

1. **`storage.py:23`** — Replace MD5 with SHA-256 (truncated to 32 chars for table name compatibility):

```diff
-path_hash = hashlib.md5(normalized_root.encode('utf-8')).hexdigest()
+path_hash = hashlib.sha256(normalized_root.encode('utf-8')).hexdigest()[:32]
```

2. **`parser.py:338`** — Replace MD5 with SHA-256 (truncated to 32 chars to maintain ID length):

```diff
-chunk_id = hashlib.md5(raw_id.encode('utf-8')).hexdigest()
+chunk_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:32]
```

3. **Verify:** After applying, perform a `force_full_scan=True` re-index to rebuild all tables with new hashes. Run full test suite.

---

### FINDING-3: Standardize Git Subprocess Environment Variables

**File:** [git_utils.py](file:///d:/Development/code-intel/src/git_utils.py)
**Risk:** Defense-in-depth against unexpected git prompts
**Effort:** ~10 min

#### Steps

1. **Create a shared env dict** at the module level:

```python
_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
}
```

2. **Apply `env=_GIT_ENV`** to all three `create_subprocess_exec` calls:
   - `is_git_repo` (line 14)
   - `get_file_git_info` (line 51)
   - `get_active_branch` (line 106) — already has it inline, replace with the shared dict

3. **Add directory existence check** before using `cwd`:

```python
abs_repo = str(Path(repo_root).resolve())
if not Path(abs_repo).is_dir():
    logger.warning(f"Repository root is not a directory: {abs_repo}")
    return {"author": None, "last_modified": None}
```

4. **Verify:** Run git-dependent tests and confirm metadata retrieval still works.

---

## Phase 3 — Cleanup (LOW Severity)

### FINDING-6: Add `.lancedb/` to `.gitignore`

**File:** [.gitignore](file:///d:/Development/code-intel/.gitignore)
**Effort:** ~1 min

#### Steps

1. Append to `.gitignore`:

```diff
+# LanceDB local store
+.lancedb/
```

2. If `.lancedb/` is already tracked, untrack it:

```bash
git rm -r --cached .lancedb/
```

---

### FINDING-7: Fix Deprecated `datetime.utcnow()`

**File:** [cache.py](file:///d:/Development/code-intel/src/cache.py)
**Effort:** ~5 min

#### Steps

1. **Add `timezone` import** at the top of the file:

```diff
-from datetime import datetime
+from datetime import datetime, timezone
```

2. **Replace both usages** (lines 72 and 85):

```diff
-datetime.utcnow()
+datetime.now(timezone.utc)
```

3. **Verify:** Run cache tests — timestamps are only used for LRU pruning, so functional behavior should be identical.

---

## Post-Remediation Checklist

- [ ] All 7 findings addressed
- [ ] Full test suite passes (`uv run pytest tests/ -v --tb=short`)
- [ ] Coverage gate met (≥80%)
- [ ] `force_full_scan=True` re-index performed (required after FINDING-5 hash migration)
- [ ] Commit changes using Conventional Commits: `fix(security): remediate findings from SECURITY_REPORT-20260223`
- [ ] Update `docs/PROGRESS.md` with security remediation status
