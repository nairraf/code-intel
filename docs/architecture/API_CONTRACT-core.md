# API Contract: Core Retrieval Behavior

## Overview
This document outlines the core retrieval behavior for [`search_code`](src/tools/search.py:19), [`find_definition`](src/tools/definition.py:46), and [`find_references`](src/tools/references.py:18), including scope tuning and Milestone 7 retrieval-precision enhancements.

## Core Principles

### 1. Glob-Based Filtering
We adopt standard glob pattern semantics (similar to `.gitignore` and `fnmatch`) to filter files.

### 2. Source-First Retrieval
When the user intent appears implementation-oriented, retrieval should prefer source files over documentation and report artifacts.

### 3. Confidence-Aware References
Reference results should communicate both the structural match type and a normalized confidence level so agents can decide when follow-up verification is needed.

### 4. Agent-Guided Discovery
Search results should expose enough metadata for downstream agents to understand whether the hit is code, test, documentation, or report content.

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
- **Limit Bounds**:
    - `limit` is clamped into a safe bounded range before retrieval.
- **Filtering**:
    - **Method A (Post-Filter)**: Retrieve `limit * X` results from DB. Filter in Python using `fnmatch`. Return top `limit`.
    - **Method B (Pre-Filter)**: Apply SQL `WHERE` clause in LanceDB.
        - *LanceDB Support*: Supports basic SQL. `WHERE filename LIKE '%pattern%'`.
        - *Challenge*: Converting complex globs (`src/**/*.py`) to SQL/LanceDB filters might be fragile.
    - **Decision for V1**: **Post-Filtering**. It's robust and predictable. We fetch `limit * 5` candidates, apply Python `fnmatch`, and return top `limit`.
- **Intent Heuristics**:
    - The query is classified into a lightweight intent family such as `implementation`, `framework`, `documentation`, or `general`.
    - Implementation and framework-oriented queries receive stronger ranking bias toward source code.
- **Ranking Bias**:
    - Source files should outrank tests, and tests should usually outrank documentation and generated report content for implementation-oriented queries.
    - Documentation-oriented queries may reduce or invert that bias.
- **Result Metadata**:
    - Each formatted result should include a result-class indicator such as `source`, `test`, `docs`, or `report`.
    - Each formatted result should include a retrieval-intent indicator when available.

### 3. `find_references`
**Purpose**: Return cross-file usages with clearer structural semantics for agents.

#### Current Signature
```python
async def find_references(
    symbol_name: str,
    root_path: str = "."
) -> str
```

#### Behavior
- **Reference Kind Semantics**:
    - Reference edges should distinguish between `import`, `call`, `dependency_injection`, `decorator`, and `instantiation` contexts where available.
- **Confidence Semantics**:
    - `explicit_import` and structurally resolved framework references should be reported as high confidence.
    - Heuristic global symbol matches should be reported as medium or low confidence depending on context.
- **Output Guidance**:
    - The formatted response should expose both normalized confidence and the underlying match type so agents can decide whether secondary verification is required.

### 4. `find_definition`
**Purpose**: Preserve source-first navigation behavior when multiple candidate definitions exist.

#### Behavior
- When multiple candidates match, the ranking should continue to prefer same-language and higher-priority implementation files over lower-signal documentation artifacts.

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
