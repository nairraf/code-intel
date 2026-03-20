# API Contract: Structural Core

## Purpose

This document defines the minimum internal contract for the new parallel structural core.

It is intentionally smaller than the current implementation surface. The goal is to prove the reboot thesis with the smallest architecture that can still deliver cheap, trustworthy structural refresh and exact structural inspection.

## Design Constraints

1. SQLite is the authority for structural refresh state.
2. The structural core must not require LanceDB for refresh decisions.
3. The structural core must prefer exact facts over heuristic inference.
4. The structural core must keep the default refresh path free of optional enrichment work.
5. The feature branch default runtime must not instantiate the legacy semantic core.

## Minimum Module Set

- `src/structural_core/models.py`
- `src/structural_core/store.py`
- `src/structural_core/manifest.py`
- `src/structural_core/refresh.py`

Additional modules may be added later, but the first pass should stay within this boundary.

## Minimum SQLite Schema

### `file_manifest`
Tracks lightweight file state for fast change detection.

Required columns:

```text
project_root TEXT
filename TEXT
size INTEGER
mtime_ns INTEGER
content_hash TEXT
PRIMARY KEY (project_root, filename)
```

### `symbols`
Stores exact structural definitions.

Required columns:

```text
project_root TEXT
symbol_id TEXT
filename TEXT
symbol_name TEXT
symbol_kind TEXT
language TEXT
parent_symbol TEXT
start_line INTEGER
end_line INTEGER
signature TEXT
PRIMARY KEY (project_root, symbol_id)
```

### `imports`
Stores exact file-level import dependencies.

Required columns:

```text
project_root TEXT
filename TEXT
import_text TEXT
resolved_path TEXT
import_kind TEXT
PRIMARY KEY (project_root, filename, import_text)
```

### `edges`
Stores exact structural relationships.

Required columns:

```text
project_root TEXT
source_symbol_id TEXT
target_symbol_id TEXT
edge_kind TEXT
source_filename TEXT
target_filename TEXT
metadata_json TEXT
PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind)
```

### `refresh_runs`
Tracks refresh visibility and trust state.

Required columns:

```text
project_root TEXT PRIMARY KEY
last_refresh_at TEXT
scan_type TEXT
status TEXT
files_scanned INTEGER
files_changed INTEGER
files_skipped INTEGER
warnings_json TEXT
```

## Minimum Python Interfaces

### `FileState`

```python
@dataclass(frozen=True)
class FileState:
    filename: str
    size: int
    mtime_ns: int
    content_hash: str = ""
```

### `ManifestDiff`

```python
@dataclass(frozen=True)
class ManifestDiff:
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]
```

### `StructuralStore`

```python
class StructuralStore:
    def get_file_manifest(self, project_root: str) -> dict[str, FileState]: ...
    def upsert_file_manifest(self, project_root: str, entries: list[FileState]) -> None: ...
    def delete_file_manifest(self, project_root: str, filenames: list[str]) -> None: ...
    def initialize_schema(self) -> None: ...
```

### `plan_refresh`

```python
def plan_refresh(
    stored_manifest: dict[str, FileState],
    observed_manifest: dict[str, FileState],
) -> ManifestDiff: ...
```

## First Port Target

The first runtime capability that must move to the new core is `refresh_index`.

The first port is considered successful when:

1. default refresh decisions are driven by the new structural core manifest
2. removed files clear structural state through the new store
3. unchanged files do not pay whole-file hashing cost
4. the refresh path does not require LanceDB to decide what changed

## Approved Branch Cutover

The approved cutover for `feature/structural-context-pivot` is:

1. `refresh_index` is structural-only by default
2. `get_stats` reads only structural-core facts
3. `search_code`, `find_definition`, and `find_references` are disabled until rebuilt on the new core
4. Ollama, LanceDB, and the legacy knowledge graph are not part of the default runtime foundation