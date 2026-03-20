from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileState:
    filename: str
    size: int
    mtime_ns: int
    content_hash: str = ""


@dataclass(frozen=True)
class ManifestDiff:
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]


@dataclass(frozen=True)
class SymbolRecord:
    project_root: str
    symbol_id: str
    filename: str
    symbol_name: str
    symbol_kind: str
    language: str
    start_line: int
    end_line: int
    parent_symbol: str = ""
    signature: str = ""


@dataclass(frozen=True)
class ImportRecord:
    project_root: str
    filename: str
    import_text: str
    resolved_path: str = ""
    import_kind: str = "import"


@dataclass(frozen=True)
class EdgeRecord:
    project_root: str
    source_symbol_id: str
    target_symbol_id: str
    edge_kind: str
    source_filename: str
    target_filename: str
    metadata_json: str = "{}"


@dataclass(frozen=True)
class RefreshRun:
    project_root: str
    last_refresh_at: str
    scan_type: str
    status: str
    files_scanned: int
    files_changed: int
    files_skipped: int
    warnings_json: str = "[]"


@dataclass(frozen=True)
class StructuralRefreshResult:
    project_root: str
    scan_type: str
    files_scanned: int
    files_changed: int
    files_skipped: int
    files_removed: int
    changed_files: tuple[str, ...] = ()
    removed_files: tuple[str, ...] = ()
    unchanged_files: tuple[str, ...] = ()
    parsed_chunks: dict[str, list] = field(default_factory=dict, repr=False)