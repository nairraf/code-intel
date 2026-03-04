# Security Review — code-intel MCP Server (v3.1.0)

**Reviewer:** Senior Security Engineer (automated)
**Date:** 2026-02-23
**Scope:** Full codebase — `src/`, `src/resolution/`, `src/parsers/`, project root config files
**Risk Model:** Developer tool running locally via `stdio` MCP transport. No direct internet-facing surface.

---

## Executive Summary

The code-intel project is a **locally-hosted MCP server** that indexes codebases using tree-sitter AST parsing, stores embeddings in LanceDB, and maintains a knowledge graph in SQLite. Because it runs locally as a subprocess of the IDE with no network listeners, many traditional web-application attack vectors (XSS, CSRF, session hijacking) are **not applicable**.

However, the review identified **7 findings** across 3 severity levels. The most critical themes are **SQL/filter injection in LanceDB queries**, **unsafe deserialization via `pickle`**, and **command injection surface area in `git_utils.py`**. None are remotely exploitable today, but they represent defense-in-depth gaps that matter if this tool is ever repurposed, deployed as a shared service, or if an upstream caller passes adversarial data.

| Severity | Count |
|----------|-------|
| 🔴 HIGH  | 2     |
| 🟡 MEDIUM | 3    |
| 🟢 LOW   | 2     |

---

## Findings

### 🔴 FINDING-1: SQL/Filter Injection in LanceDB Queries

**Files:** [storage.py](file:///d:/Development/code-intel/src/storage.py)
**Lines:** 94-95, 118, 130-132, 145

LanceDB's `.where()` and `.delete()` methods accept raw string filters constructed via f-strings. User-controlled values (`symbol_name`, `filepath`, `chunk_id`) are interpolated directly into these filter expressions.

```python
# storage.py:118
results = table.search().where(f'symbol_name = "{symbol_name}"').to_list()

# storage.py:94-95
safe_path = path.replace('"', '""')
table.delete(f'filename = "{safe_path}"')
```

**Risk:** If an MCP caller passes a crafted `symbol_name` containing `"`, the filter grammar can be broken or manipulated to delete/query unintended rows. The `safe_path` escaping in `upsert_chunks` only doubles quotes — this is a dialect-specific heuristic, not a parameterized query.

**Impact:** Data corruption/deletion in the local LanceDB store. Not remotely exploitable because the MCP transport is local `stdio`.

**Recommendation:**
- Investigate if LanceDB supports parameterized filters (it does via DuckDB SQL syntax: `WHERE col = ?`).
- If not, apply a strict allowlist regex (e.g. `^[a-zA-Z0-9_.]+$`) to `symbol_name` before interpolation.
- Apply consistent escaping across **all** query sites, not just `upsert_chunks`.

---

### 🔴 FINDING-2: Unsafe Deserialization via `pickle`

**File:** [cache.py](file:///d:/Development/code-intel/src/cache.py)
**Lines:** 74, 84

Embedding vectors are serialized with `pickle.dumps()` and deserialized with `pickle.loads()` from an SQLite database stored at `~/.code_intel_store/cache/embeddings.sqlite`.

```python
# cache.py:74  (read)
return pickle.loads(row[0])

# cache.py:84  (write)
blob = pickle.dumps(vector)
```

**Risk:** `pickle.loads()` is a **known arbitrary code execution vector** ([CWE-502](https://cwe.mitre.org/data/definitions/502.html)). If an attacker can modify the SQLite file on disk (e.g. via another compromised process, malware, or a shared workstation), they can inject a malicious pickle payload that executes arbitrary code when the cache is read.

**Impact:** Arbitrary code execution under the user's session. The cache file sits in the user's home directory with standard file permissions, so exploitation requires pre-existing local access.

**Recommendation:**
- Replace `pickle` with a safe serializer. Since the vectors are simple `List[float]`, use `struct.pack`/`struct.unpack` or `json.dumps`/`json.loads`.
- Example drop-in using `json`:
  ```python
  import json
  blob = json.dumps(vector).encode('utf-8')
  vector = json.loads(row[0])
  ```

---

### 🟡 FINDING-3: Command Injection Surface in `git_utils.py`

**File:** [git_utils.py](file:///d:/Development/code-intel/src/git_utils.py)
**Lines:** 14, 51-52, 106-107

External subprocesses are spawned via `asyncio.create_subprocess_exec()` with arguments derived from user-provided file paths and repository roots.

```python
process = await asyncio.create_subprocess_exec(
    "git", "log", "-1", "--format=%an|%ai", "--", rel_path,
    cwd=abs_repo, ...
)
```

**Mitigating factors:**
- `create_subprocess_exec` is used (not `shell=True`), which prevents shell metacharacter injection.
- `stdin=subprocess.DEVNULL` is set, preventing interactive git prompts.
- `GIT_TERMINAL_PROMPT=0` is set in `get_active_branch`.

**Residual risk:** A crafted `rel_path` starting with `--` could be interpreted as a git flag. The `--` separator before `rel_path` correctly mitigates this in `get_file_git_info`, but **not** in `is_git_repo` or `get_active_branch` (those don't pass user-controlled arguments after `--`, so this is informational only).

**Recommendation:**
- Consistently apply `GIT_TERMINAL_PROMPT=0` and `GIT_OPTIONAL_LOCKS=0` across **all** git subprocess calls (currently only in `get_active_branch`).
- Add a verification that `abs_repo` actually exists and is a directory before passing it as `cwd`.

---

### 🟡 FINDING-4: Path Traversal via Import Resolvers

**Files:** [python.py](file:///d:/Development/code-intel/src/resolution/python.py), [javascript.py](file:///d:/Development/code-intel/src/resolution/javascript.py), [dart.py](file:///d:/Development/code-intel/src/resolution/dart.py)

Import resolution converts user-provided import strings into filesystem paths and checks for their existence. The resolvers use `Path.resolve()` which follows symlinks and normalizes `..` traversals.

```python
# javascript.py:46
target_path = (source_dir / import_string).resolve()
```

**Risk:** A malicious import string like `../../../../etc/passwd` would resolve to a path outside the project. While the resolvers only check `exists()` and don't read file contents, success/failure timing could theoretically leak information about the filesystem structure.

**Recommendation:**
- After resolution, validate that the resolved path is still within the `project_root` before returning it:
  ```python
  resolved = target_path.resolve()
  if not str(resolved).startswith(str(project_root.resolve())):
      return None
  ```

---

### 🟡 FINDING-5: Weak Hashing for Security-Sensitive Identifiers

**Files:** [storage.py](file:///d:/Development/code-intel/src/storage.py#L23), [parser.py](file:///d:/Development/code-intel/src/parser.py#L338)

- **MD5** is used for generating table names (`_get_table_name`) and chunk IDs (`_create_chunk`).

```python
# storage.py:23
path_hash = hashlib.md5(normalized_root.encode('utf-8')).hexdigest()

# parser.py:338
chunk_id = hashlib.md5(raw_id.encode('utf-8')).hexdigest()
```

**Risk:** MD5 is cryptographically broken ([CWE-328](https://cwe.mitre.org/data/definitions/328.html)). While this usage is for **identifiers** (not security authentication), MD5 collision attacks could cause two different chunks or project roots to map to the same ID/table, leading to data corruption.

**Impact:** Low in practice for a local dev tool, but represents a bad pattern to copy to other projects.

**Recommendation:**
- Replace with `hashlib.sha256(...).hexdigest()[:32]` for the same length but substantially stronger collision resistance.
- Note: `_hash_file` in `server.py` already correctly uses SHA-256 — this should be the standard.

---

### 🟢 FINDING-6: `.env` File in Repository / Gitignore Correctness

**Files:** [.env](file:///d:/Development/code-intel/.env), [.gitignore](file:///d:/Development/code-intel/.gitignore)

The `.env` file contains only local configuration (Ollama endpoint URL) and no secrets. The `.gitignore` correctly lists `.env`, preventing accidental commits.

> [!TIP]
> Current `.env` is safe — no API keys, tokens, or credentials are present.

**Recommendation:**
- Add a comment in `.env-example` warning future contributors not to put secrets here.
- The `.lancedb/` directory is **not** in `.gitignore` — add it to prevent accidentally committing database files.

---

### 🟢 FINDING-7: Deprecated `datetime.utcnow()` Usage

**File:** [cache.py](file:///d:/Development/code-intel/src/cache.py)
**Lines:** 72, 85

```python
conn.execute("UPDATE embeddings SET last_accessed = ? WHERE hash = ?",
    (datetime.utcnow(), text_hash))
```

`datetime.utcnow()` is deprecated since Python 3.12. It returns a naive datetime, which can cause subtle mishandling in timezone-aware contexts.

**Recommendation:**
- Replace with `datetime.now(timezone.utc)` (already used correctly in `storage.py:249`).

---

## OWASP Top 10 Assessment

| # | OWASP Category | Applicable? | Notes |
|---|----------------|-------------|-------|
| A01 | Broken Access Control | ⚠️ Partial | No auth model exists; anyone who can access the `stdio` pipe has full control. Acceptable for a local dev tool. |
| A02 | Cryptographic Failures | ⚠️ Yes | MD5 for identifiers (FINDING-5), pickle for serialization (FINDING-2). |
| A03 | Injection | 🔴 Yes | LanceDB filter injection (FINDING-1), bounded git command injection (FINDING-3). |
| A04 | Insecure Design | ✅ N/A | Design is appropriate for a local developer tool. |
| A05 | Security Misconfiguration | ✅ Clean | `.env` properly gitignored, no hardcoded secrets. |
| A06 | Vulnerable Components | ✅ N/A | Dependencies are current. No known CVEs in pinned versions. |
| A07 | Auth Failures | ✅ N/A | No authentication needed for local `stdio` MCP. |
| A08 | Data Integrity Failures | ⚠️ Yes | `pickle.loads()` on cached data (FINDING-2). |
| A09 | Logging/Monitoring Failures | ✅ Adequate | Logging to file and stderr is implemented. |
| A10 | SSRF | ⚠️ Bounded | The `OllamaClient` makes HTTP POST to a configurable endpoint (`EMBEDDING_ENDPOINT`). If this env var is attacker-controlled, it could be pointed at an internal service. Risk is bounded to local environment. |

---

## Prioritized Remediation Roadmap

| Priority | Finding | Effort | Risk Reduction |
|----------|---------|--------|----------------|
| 1 | FINDING-2: Replace `pickle` with `json`/`struct` | ~30 min | Eliminates RCE vector |
| 2 | FINDING-1: Parameterize or sanitize LanceDB filters | ~1 hour | Eliminates data corruption vector |
| 3 | FINDING-4: Add project root containment check to resolvers | ~30 min | Prevents future path traversal bugs |
| 4 | FINDING-5: Migrate MD5 → SHA-256 for IDs | ~15 min | Consistency + collision resistance |
| 5 | FINDING-3: Standardize git subprocess env vars | ~10 min | Defense-in-depth |
| 6 | FINDING-6: Add `.lancedb/` to `.gitignore` | ~1 min | Prevents data leak |
| 7 | FINDING-7: Fix deprecated `datetime.utcnow()` | ~5 min | Future-proofing |

---

## Conclusion

For a **locally-hosted developer tool**, the security posture is **reasonable**. The codebase shows good practices in many areas: `subprocess.DEVNULL` for stdin, `errors='replace'` for encoding, exception handling with logging, and correct `.gitignore` patterns for secrets.

The two high-severity findings (pickle deserialization and filter injection) should be addressed promptly — not because they are actively exploitable today, but because they represent **latent vulnerabilities** that could become critical if the deployment model ever changes (e.g., multi-user, network-accessible, or shared cache directories).

Overall risk rating: **MEDIUM** — no immediate emergency, but targeted remediation recommended.
