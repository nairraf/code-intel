# API Contract: Scope Tuning Features

## Overview
This document outlines the API changes required to support Scope Tuning (file filtering) in `code-intel`.

## Core Principle: Glob-Based Filtering
We will adopt standard glob pattern semantics (similar to `.gitignore` and `fnmatch`) to filter files.

### Syntax
- `*`: Matches any sequence of characters (excluding path separators).
- `?`: Matches any single character.
- `**`: Matches directories recursively.
- `[seq]`: Matches any character in seq.
- `[!seq]`: Matches any character not in seq.

### Path Resolution
- All globs are matched against the **file path relative to the project root**.
- Leading slashes (`/foo`) anchor to the project root.
- No leading slash (`foo`) matches anywhere in the tree (unless containing path separators).

## Tool Updates

### 1. `refresh_index`
**Purpose**: Update index with strict control over what gets scanned.

#### New Signature
```python
async def refresh_index(
    root_path: str = ".",
    force_full_scan: bool = False,
    include: str = None,  # Glob pattern
    exclude: str = None   # Glob pattern
) -> str
```

#### Behavior
- `include`: If provided, ONLY files matching this glob are indexed. If `None` (default), all supported files are candidates.
- `exclude`: Files matching this glob are SKIPPED, even if they match `include`.
- **Precedence**: `exclude` > `include`.
- **Defaults**: `src/config.py:IGNORE_DIRS` are ALWAYS excluded unless explicitly overridden (TBD: do we want to allow overriding system ignores?). *Decision: System ignores are hard rules. Excludes add to them.*

### 2. `search_code`
**Purpose**: Reduce noise in search results.

#### New Signature
```python
async def search_code(
    query: str,
    root_path: str = ".",
    limit: int = 10,
    include: str = None,  # Glob pattern
    exclude: str = None   # Glob pattern
) -> str
```

#### Behavior
- **Backend**: Vector search retrieves chunks.
- **Filtering**:
    - **Method A (Post-Filter)**: Retrieve `limit * X` results from DB. Filter in Python using `fnmatch`. Return top `limit`.
    - **Method B (Pre-Filter)**: Apply SQL `WHERE` clause in LanceDB.
        - *LanceDB Support*: Supports basic SQL. `WHERE filename LIKE '%pattern%'`.
        - *Challenge*: Converting complex globs (`src/**/*.py`) to SQL/LanceDB filters might be fragile.
    - **Decision for V1**: **Post-Filtering**. It's robust and predictable. We fetch `limit * 5` candidates, apply Python `fnmatch`, and return top `limit`.

---

## Example Usage

**Scenario**: "Search for 'authentication' but ignore tests."
```python
# User Query
search_code("authentication", exclude="tests/**")
```

**Scenario**: "Re-index only the 'security' module."
```python
# User Command
refresh_index(include="src/security/**")
```
