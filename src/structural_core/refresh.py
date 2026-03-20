from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from ..models import CodeChunk
from ..parser import CodeParser
from ..resolution.dart import DartImportResolver
from ..resolution.javascript import JSImportResolver
from ..resolution.python import PythonImportResolver
from ..utils import normalize_path
from .manifest import get_file_state, plan_refresh
from .models import EdgeRecord, FileState, ImportRecord, ManifestDiff, RefreshRun, StructuralRefreshResult, SymbolRecord
from .store import StructuralStore


class StructuralRefreshPlanner:
    def __init__(self, store: StructuralStore):
        self.store = store

    def collect_observed_manifest(self, filepaths: Iterable[str]) -> dict[str, FileState]:
        observed: dict[str, FileState] = {}
        for filepath in filepaths:
            state = get_file_state(filepath)
            if state is not None:
                observed[state.filename] = state
        return observed

    def plan(self, project_root: str, filepaths: Iterable[str]) -> ManifestDiff:
        stored_manifest = self.store.get_file_manifest(project_root)
        observed_manifest = self.collect_observed_manifest(filepaths)
        return plan_refresh(stored_manifest, observed_manifest)


class StructuralRefresher:
    def __init__(self, store: StructuralStore, parser: CodeParser):
        self.store = store
        self.parser = parser
        self.planner = StructuralRefreshPlanner(store)
        self.resolvers = {
            "python": PythonImportResolver(),
            "javascript": JSImportResolver(),
            "typescript": JSImportResolver(),
            "tsx": JSImportResolver(),
            "dart": DartImportResolver(),
        }

    def refresh(
        self,
        project_root: str,
        filepaths: Iterable[str],
        force_full_scan: bool = False,
        prune_missing_files: bool = True,
    ) -> StructuralRefreshResult:
        normalized_root = normalize_path(project_root)
        normalized_filepaths = [normalize_path(filepath) for filepath in filepaths]

        if force_full_scan:
            self.store.clear_project(normalized_root)

        observed_manifest = self.planner.collect_observed_manifest(normalized_filepaths)
        stored_manifest = self.store.get_file_manifest(normalized_root)
        if not prune_missing_files:
            stored_manifest = {
                filename: state
                for filename, state in stored_manifest.items()
                if filename in normalized_filepaths
            }
        diff = plan_refresh(stored_manifest, observed_manifest)
        changed_files = list(diff.added) + list(diff.changed)
        parsed_chunks: dict[str, list[CodeChunk]] = {}
        invalidated_files = list(changed_files) + list(diff.removed)
        impacted_source_files = [
            filename
            for filename in self.store.get_source_files(normalized_root, invalidated_files)
            if filename not in invalidated_files and Path(filename).exists()
        ]

        if diff.removed:
            self.store.delete_files(normalized_root, list(diff.removed))

        for filename in changed_files:
            chunks = self.parser.parse_file(filename, project_root=normalized_root)
            parsed_chunks[filename] = chunks
            symbols = _extract_symbol_records(normalized_root, filename, chunks)
            imports = _extract_import_records(normalized_root, filename, chunks)
            self.store.replace_file_symbols(normalized_root, filename, symbols)
            self.store.replace_file_imports(normalized_root, filename, imports)

        files_to_link = list(changed_files)
        files_to_link.extend(filename for filename in impacted_source_files if filename not in files_to_link)
        edge_count = 0
        for filename in files_to_link:
            chunks = parsed_chunks.get(filename)
            if chunks is None:
                chunks = self.parser.parse_file(filename, project_root=normalized_root)
                parsed_chunks[filename] = chunks
            edges = self._build_exact_edges(normalized_root, filename, chunks)
            self.store.replace_file_edges(normalized_root, filename, edges)
            edge_count += len(edges)

        manifest_entries = [observed_manifest[filename] for filename in changed_files if filename in observed_manifest]
        if manifest_entries:
            self.store.upsert_file_manifest(normalized_root, manifest_entries)

        refresh_run = RefreshRun(
            project_root=normalized_root,
            last_refresh_at=datetime.now(timezone.utc).isoformat(),
            scan_type="full" if force_full_scan else "incremental",
            status="ok",
            files_scanned=len(tuple(normalized_filepaths)),
            files_changed=len(changed_files) + len(diff.removed),
            files_skipped=len(diff.unchanged),
        )
        self.store.upsert_refresh_run(refresh_run)

        return StructuralRefreshResult(
            project_root=normalized_root,
            scan_type=refresh_run.scan_type,
            files_scanned=refresh_run.files_scanned,
            files_changed=refresh_run.files_changed,
            files_skipped=refresh_run.files_skipped,
            files_removed=len(diff.removed),
            changed_files=tuple(changed_files),
            removed_files=diff.removed,
            unchanged_files=diff.unchanged,
            parsed_chunks=parsed_chunks,
        )

    def _build_exact_edges(
        self,
        project_root: str,
        filename: str,
        chunks: list[CodeChunk],
    ) -> list[EdgeRecord]:
        edge_records: list[EdgeRecord] = []
        local_symbols = self.store.list_symbols(project_root, filename)
        local_by_name: dict[str, list[SymbolRecord]] = {}
        for symbol in local_symbols:
            local_by_name.setdefault(symbol.symbol_name, []).append(symbol)

        language_name = chunks[0].language if chunks else self.parser.ext_map.get(Path(filename).suffix.lower(), "")
        resolver = self.resolvers.get(language_name)
        project_root_path = Path(project_root)

        for chunk in chunks:
            if not chunk.usages:
                continue

            for usage in chunk.usages:
                target_symbols = self._resolve_usage_targets(
                    project_root,
                    filename,
                    chunk,
                    usage,
                    local_by_name,
                    resolver,
                    project_root_path,
                )
                for target_symbol, match_type in target_symbols:
                    if target_symbol.symbol_id == chunk.id:
                        continue
                    edge_records.append(
                        EdgeRecord(
                            project_root=project_root,
                            source_symbol_id=chunk.id,
                            target_symbol_id=target_symbol.symbol_id,
                            edge_kind="call",
                            source_filename=filename,
                            target_filename=target_symbol.filename,
                            metadata_json=json.dumps(
                                {
                                    "context": usage.context,
                                    "line": usage.line,
                                    "character": usage.character,
                                    "match_type": match_type,
                                },
                                sort_keys=True,
                            ),
                        )
                    )

        unique_edges: dict[tuple[str, str, str, str], EdgeRecord] = {}
        for edge in edge_records:
            key = (edge.source_symbol_id, edge.target_symbol_id, edge.edge_kind, edge.metadata_json)
            unique_edges[key] = edge
        return list(unique_edges.values())

    def _resolve_usage_targets(
        self,
        project_root: str,
        filename: str,
        chunk: CodeChunk,
        usage,
        local_by_name: dict[str, list[SymbolRecord]],
        resolver,
        project_root_path: Path,
    ) -> list[tuple[SymbolRecord, str]]:
        exact_targets: list[tuple[SymbolRecord, str]] = []

        for symbol in local_by_name.get(usage.name, []):
            exact_targets.append((symbol, "local_symbol"))

        if resolver and chunk.dependencies:
            for dependency in chunk.dependencies:
                if "::" not in dependency:
                    continue
                module_name, imported_symbol = dependency.split("::", 1)
                if imported_symbol != usage.name:
                    continue
                resolved_path = resolver.resolve(filename, module_name, project_root=project_root_path)
                if not resolved_path:
                    continue
                for symbol in self.store.list_symbols(project_root, resolved_path):
                    if symbol.symbol_name == usage.name and symbol.language == chunk.language:
                        exact_targets.append((symbol, "explicit_import"))

        return exact_targets


def _extract_symbol_records(project_root: str, filename: str, chunks: list[CodeChunk]) -> list[SymbolRecord]:
    records: list[SymbolRecord] = []
    normalized_filename = normalize_path(filename)
    for chunk in chunks:
        if not chunk.symbol_name:
            continue
        records.append(
            SymbolRecord(
                project_root=project_root,
                symbol_id=chunk.id,
                filename=normalized_filename,
                symbol_name=chunk.symbol_name,
                symbol_kind=chunk.type,
                language=chunk.language,
                parent_symbol=chunk.parent_symbol or "",
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                signature=chunk.signature or "",
            )
        )
    return records


def _extract_import_records(project_root: str, filename: str, chunks: list[CodeChunk]) -> list[ImportRecord]:
    normalized_filename = normalize_path(filename)
    dependencies = sorted({dependency for chunk in chunks for dependency in chunk.dependencies})
    return [
        ImportRecord(
            project_root=project_root,
            filename=normalized_filename,
            import_text=dependency,
            import_kind="explicit_symbol" if "::" in dependency else "import",
        )
        for dependency in dependencies
    ]