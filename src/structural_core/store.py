import sqlite3
from dataclasses import asdict
from pathlib import Path

from ..config import CACHE_DIR
from ..utils import normalize_path
from .models import EdgeRecord, FileState, ImportRecord, RefreshRun, SymbolRecord


class StructuralStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(CACHE_DIR / "structural_core.sqlite")
        self._conn: sqlite3.Connection | None = None
        self.initialize_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            db_parent = Path(self.db_path).parent
            db_parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def initialize_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS file_manifest (
                project_root TEXT NOT NULL,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (project_root, filename)
            );

            CREATE TABLE IF NOT EXISTS symbols (
                project_root TEXT NOT NULL,
                symbol_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                symbol_name TEXT NOT NULL,
                symbol_kind TEXT NOT NULL,
                language TEXT NOT NULL,
                parent_symbol TEXT NOT NULL DEFAULT '',
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                signature TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (project_root, symbol_id)
            );

            CREATE TABLE IF NOT EXISTS imports (
                project_root TEXT NOT NULL,
                filename TEXT NOT NULL,
                import_text TEXT NOT NULL,
                resolved_path TEXT NOT NULL DEFAULT '',
                import_kind TEXT NOT NULL DEFAULT 'import',
                PRIMARY KEY (project_root, filename, import_text)
            );

            CREATE TABLE IF NOT EXISTS edges (
                project_root TEXT NOT NULL,
                source_symbol_id TEXT NOT NULL,
                target_symbol_id TEXT NOT NULL,
                edge_kind TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                target_filename TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind, metadata_json)
            );

            CREATE TABLE IF NOT EXISTS refresh_runs (
                project_root TEXT PRIMARY KEY,
                last_refresh_at TEXT NOT NULL,
                scan_type TEXT NOT NULL,
                status TEXT NOT NULL,
                files_scanned INTEGER NOT NULL,
                files_changed INTEGER NOT NULL,
                files_skipped INTEGER NOT NULL,
                warnings_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        self._migrate_legacy_edges_table(conn)
        conn.commit()

    def _migrate_legacy_edges_table(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'edges'"
        ).fetchone()
        if row is None:
            return

        create_sql = (row[0] or "").replace("\n", " ")
        expected_pk = "PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind, metadata_json)"
        if expected_pk in create_sql:
            return

        conn.execute("ALTER TABLE edges RENAME TO edges_legacy")
        conn.execute(
            """
            CREATE TABLE edges (
                project_root TEXT NOT NULL,
                source_symbol_id TEXT NOT NULL,
                target_symbol_id TEXT NOT NULL,
                edge_kind TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                target_filename TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind, metadata_json)
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO edges (
                project_root, source_symbol_id, target_symbol_id, edge_kind,
                source_filename, target_filename, metadata_json
            )
            SELECT DISTINCT
                project_root,
                source_symbol_id,
                target_symbol_id,
                edge_kind,
                source_filename,
                target_filename,
                COALESCE(metadata_json, '{}')
            FROM edges_legacy
            """
        )
        conn.execute("DROP TABLE edges_legacy")

    def list_tables(self) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def get_file_manifest(self, project_root: str) -> dict[str, FileState]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT filename, size, mtime_ns, content_hash
            FROM file_manifest
            WHERE project_root = ?
            ORDER BY filename
            """,
            (normalized_root,),
        ).fetchall()
        return {
            row["filename"]: FileState(
                filename=row["filename"],
                size=int(row["size"]),
                mtime_ns=int(row["mtime_ns"]),
                content_hash=row["content_hash"] or "",
            )
            for row in rows
        }

    def upsert_file_manifest(self, project_root: str, entries: list[FileState]) -> None:
        if not entries:
            return

        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        conn.executemany(
            """
            INSERT INTO file_manifest (project_root, filename, size, mtime_ns, content_hash)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_root, filename) DO UPDATE SET
                size = excluded.size,
                mtime_ns = excluded.mtime_ns,
                content_hash = excluded.content_hash
            """,
            [
                (
                    normalized_root,
                    normalize_path(entry.filename),
                    int(entry.size),
                    int(entry.mtime_ns),
                    entry.content_hash,
                )
                for entry in entries
            ],
        )
        conn.commit()

    def delete_file_manifest(self, project_root: str, filenames: list[str]) -> None:
        if not filenames:
            return

        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        conn.executemany(
            "DELETE FROM file_manifest WHERE project_root = ? AND filename = ?",
            [(normalized_root, normalize_path(filename)) for filename in filenames],
        )
        conn.commit()

    def replace_file_symbols(self, project_root: str, filename: str, symbols: list[SymbolRecord]) -> None:
        normalized_root = normalize_path(project_root)
        normalized_file = normalize_path(filename)
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM symbols WHERE project_root = ? AND filename = ?",
            (normalized_root, normalized_file),
        )
        if symbols:
            conn.executemany(
                """
                INSERT INTO symbols (
                    project_root, symbol_id, filename, symbol_name, symbol_kind,
                    language, parent_symbol, start_line, end_line, signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized_root,
                        symbol.symbol_id,
                        normalize_path(symbol.filename),
                        symbol.symbol_name,
                        symbol.symbol_kind,
                        symbol.language,
                        symbol.parent_symbol,
                        symbol.start_line,
                        symbol.end_line,
                        symbol.signature,
                    )
                    for symbol in symbols
                ],
            )
        conn.commit()

    def replace_file_imports(self, project_root: str, filename: str, imports: list[ImportRecord]) -> None:
        normalized_root = normalize_path(project_root)
        normalized_file = normalize_path(filename)
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM imports WHERE project_root = ? AND filename = ?",
            (normalized_root, normalized_file),
        )
        if imports:
            conn.executemany(
                """
                INSERT INTO imports (
                    project_root, filename, import_text, resolved_path, import_kind
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized_root,
                        normalize_path(record.filename),
                        record.import_text,
                        record.resolved_path,
                        record.import_kind,
                    )
                    for record in imports
                ],
            )
        conn.commit()

    def list_symbols(self, project_root: str, filename: str | None = None) -> list[SymbolRecord]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        query = (
            "SELECT project_root, symbol_id, filename, symbol_name, symbol_kind, language, "
            "parent_symbol, start_line, end_line, signature FROM symbols WHERE project_root = ?"
        )
        params: list[object] = [normalized_root]
        if filename is not None:
            query += " AND filename = ?"
            params.append(normalize_path(filename))
        query += " ORDER BY filename, start_line, symbol_name"
        rows = conn.execute(query, params).fetchall()
        return [SymbolRecord(**dict(row)) for row in rows]

    def find_qualified_symbols(
        self,
        project_root: str,
        qualified_name: str,
        filename: str | None = None,
    ) -> list[SymbolRecord]:
        if "." not in qualified_name:
            return []

        parent_symbol, symbol_name = qualified_name.rsplit(".", 1)
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        query = (
            "SELECT project_root, symbol_id, filename, symbol_name, symbol_kind, language, "
            "parent_symbol, start_line, end_line, signature FROM symbols "
            "WHERE project_root = ? AND symbol_name = ? AND parent_symbol = ?"
        )
        params: list[object] = [normalized_root, symbol_name, parent_symbol.split(".")[-1]]
        if filename is not None:
            query += " AND filename = ?"
            params.append(normalize_path(filename))
        query += " ORDER BY filename, start_line, end_line"
        rows = conn.execute(query, params).fetchall()
        return [SymbolRecord(**dict(row)) for row in rows]

    def find_symbols(
        self,
        project_root: str,
        symbol_name: str,
        filename: str | None = None,
    ) -> list[SymbolRecord]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        query = (
            "SELECT project_root, symbol_id, filename, symbol_name, symbol_kind, language, "
            "parent_symbol, start_line, end_line, signature FROM symbols "
            "WHERE project_root = ? AND symbol_name = ?"
        )
        params: list[object] = [normalized_root, symbol_name]
        if filename is not None:
            query += " AND filename = ?"
            params.append(normalize_path(filename))
        query += " ORDER BY filename, start_line, end_line"
        rows = conn.execute(query, params).fetchall()
        return [SymbolRecord(**dict(row)) for row in rows]

    def get_symbol_by_id(self, project_root: str, symbol_id: str) -> SymbolRecord | None:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT project_root, symbol_id, filename, symbol_name, symbol_kind, language,
                   parent_symbol, start_line, end_line, signature
            FROM symbols
            WHERE project_root = ? AND symbol_id = ?
            """,
            (normalized_root, symbol_id),
        ).fetchone()
        if row is None:
            return None
        return SymbolRecord(**dict(row))

    def list_imports(self, project_root: str, filename: str | None = None) -> list[ImportRecord]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        query = (
            "SELECT project_root, filename, import_text, resolved_path, import_kind "
            "FROM imports WHERE project_root = ?"
        )
        params: list[object] = [normalized_root]
        if filename is not None:
            query += " AND filename = ?"
            params.append(normalize_path(filename))
        query += " ORDER BY filename, import_text"
        rows = conn.execute(query, params).fetchall()
        return [ImportRecord(**dict(row)) for row in rows]

    def replace_file_edges(self, project_root: str, filename: str, edges: list[EdgeRecord]) -> None:
        normalized_root = normalize_path(project_root)
        normalized_file = normalize_path(filename)
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM edges WHERE project_root = ? AND source_filename = ?",
            (normalized_root, normalized_file),
        )
        if edges:
            conn.executemany(
                """
                INSERT INTO edges (
                    project_root, source_symbol_id, target_symbol_id, edge_kind,
                    source_filename, target_filename, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized_root,
                        edge.source_symbol_id,
                        edge.target_symbol_id,
                        edge.edge_kind,
                        normalize_path(edge.source_filename),
                        normalize_path(edge.target_filename),
                        edge.metadata_json,
                    )
                    for edge in edges
                ],
            )
        conn.commit()

    def list_edges(
        self,
        project_root: str,
        source_filename: str | None = None,
        target_filename: str | None = None,
        edge_kind: str | None = None,
    ) -> list[EdgeRecord]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        query = (
            "SELECT project_root, source_symbol_id, target_symbol_id, edge_kind, "
            "source_filename, target_filename, metadata_json FROM edges WHERE project_root = ?"
        )
        params: list[object] = [normalized_root]
        if source_filename is not None:
            query += " AND source_filename = ?"
            params.append(normalize_path(source_filename))
        if target_filename is not None:
            query += " AND target_filename = ?"
            params.append(normalize_path(target_filename))
        if edge_kind is not None:
            query += " AND edge_kind = ?"
            params.append(edge_kind)
        query += " ORDER BY source_filename, target_filename, source_symbol_id"
        rows = conn.execute(query, params).fetchall()
        return [EdgeRecord(**dict(row)) for row in rows]

    def list_incoming_edges(
        self,
        project_root: str,
        target_symbol_ids: list[str],
        edge_kind: str | None = None,
    ) -> list[EdgeRecord]:
        if not target_symbol_ids:
            return []

        normalized_root = normalize_path(project_root)
        placeholders = ", ".join("?" for _ in target_symbol_ids)
        conn = self._get_conn()
        query = (
            "SELECT project_root, source_symbol_id, target_symbol_id, edge_kind, "
            "source_filename, target_filename, metadata_json FROM edges "
            f"WHERE project_root = ? AND target_symbol_id IN ({placeholders})"
        )
        params: list[object] = [normalized_root, *target_symbol_ids]
        if edge_kind is not None:
            query += " AND edge_kind = ?"
            params.append(edge_kind)
        query += " ORDER BY source_filename, target_filename, source_symbol_id"
        rows = conn.execute(query, params).fetchall()
        return [EdgeRecord(**dict(row)) for row in rows]

    def list_outgoing_edges(
        self,
        project_root: str,
        source_symbol_ids: list[str],
        edge_kind: str | None = None,
    ) -> list[EdgeRecord]:
        if not source_symbol_ids:
            return []

        normalized_root = normalize_path(project_root)
        placeholders = ", ".join("?" for _ in source_symbol_ids)
        conn = self._get_conn()
        query = (
            "SELECT project_root, source_symbol_id, target_symbol_id, edge_kind, "
            "source_filename, target_filename, metadata_json FROM edges "
            f"WHERE project_root = ? AND source_symbol_id IN ({placeholders})"
        )
        params: list[object] = [normalized_root, *source_symbol_ids]
        if edge_kind is not None:
            query += " AND edge_kind = ?"
            params.append(edge_kind)
        query += " ORDER BY source_filename, target_filename, source_symbol_id"
        rows = conn.execute(query, params).fetchall()
        return [EdgeRecord(**dict(row)) for row in rows]

    def list_tracked_files(self, project_root: str) -> list[str]:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT filename FROM file_manifest WHERE project_root = ? ORDER BY filename",
            (normalized_root,),
        ).fetchall()
        return [row["filename"] for row in rows]

    def get_source_files(self, project_root: str, target_filenames: list[str]) -> list[str]:
        if not target_filenames:
            return []

        normalized_root = normalize_path(project_root)
        normalized_targets = [normalize_path(filename) for filename in target_filenames]
        placeholders = ", ".join("?" for _ in normalized_targets)
        conn = self._get_conn()
        rows = conn.execute(
            f"""
            SELECT DISTINCT source_filename
            FROM edges
            WHERE project_root = ? AND target_filename IN ({placeholders})
            ORDER BY source_filename
            """,
            [normalized_root, *normalized_targets],
        ).fetchall()
        return [row["source_filename"] for row in rows]

    def delete_files(self, project_root: str, filenames: list[str]) -> None:
        if not filenames:
            return

        normalized_root = normalize_path(project_root)
        normalized_files = [normalize_path(filename) for filename in filenames]
        conn = self._get_conn()
        for normalized_file in normalized_files:
            conn.execute(
                "DELETE FROM file_manifest WHERE project_root = ? AND filename = ?",
                (normalized_root, normalized_file),
            )
            conn.execute(
                "DELETE FROM symbols WHERE project_root = ? AND filename = ?",
                (normalized_root, normalized_file),
            )
            conn.execute(
                "DELETE FROM imports WHERE project_root = ? AND filename = ?",
                (normalized_root, normalized_file),
            )
            conn.execute(
                "DELETE FROM edges WHERE project_root = ? AND (source_filename = ? OR target_filename = ?)",
                (normalized_root, normalized_file, normalized_file),
            )
        conn.commit()

    def upsert_refresh_run(self, refresh_run: RefreshRun) -> None:
        conn = self._get_conn()
        row = asdict(refresh_run)
        conn.execute(
            """
            INSERT INTO refresh_runs (
                project_root, last_refresh_at, scan_type, status,
                files_scanned, files_changed, files_skipped, warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_root) DO UPDATE SET
                last_refresh_at = excluded.last_refresh_at,
                scan_type = excluded.scan_type,
                status = excluded.status,
                files_scanned = excluded.files_scanned,
                files_changed = excluded.files_changed,
                files_skipped = excluded.files_skipped,
                warnings_json = excluded.warnings_json
            """,
            (
                normalize_path(row["project_root"]),
                row["last_refresh_at"],
                row["scan_type"],
                row["status"],
                row["files_scanned"],
                row["files_changed"],
                row["files_skipped"],
                row["warnings_json"],
            ),
        )
        conn.commit()

    def get_refresh_run(self, project_root: str) -> RefreshRun | None:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT project_root, last_refresh_at, scan_type, status,
                   files_scanned, files_changed, files_skipped, warnings_json
            FROM refresh_runs
            WHERE project_root = ?
            """,
            (normalized_root,),
        ).fetchone()
        if row is None:
            return None
        return RefreshRun(**dict(row))

    def get_project_stats(self, project_root: str) -> dict | None:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()

        tracked_files = int(
            conn.execute(
                "SELECT COUNT(*) FROM file_manifest WHERE project_root = ?",
                (normalized_root,),
            ).fetchone()[0]
        )
        symbol_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM symbols WHERE project_root = ?",
                (normalized_root,),
            ).fetchone()[0]
        )
        import_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM imports WHERE project_root = ?",
                (normalized_root,),
            ).fetchone()[0]
        )
        edge_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM edges WHERE project_root = ?",
                (normalized_root,),
            ).fetchone()[0]
        )
        refresh_run = self.get_refresh_run(normalized_root)

        if tracked_files == 0 and symbol_count == 0 and import_count == 0 and refresh_run is None:
            return None

        language_rows = conn.execute(
            """
            SELECT language, COUNT(*) AS count
            FROM symbols
            WHERE project_root = ?
            GROUP BY language
            ORDER BY count DESC, language ASC
            """,
            (normalized_root,),
        ).fetchall()
        dependency_rows = conn.execute(
            """
            SELECT import_text, COUNT(*) AS count
            FROM imports
            WHERE project_root = ?
            GROUP BY import_text
            ORDER BY count DESC, import_text ASC
            LIMIT 5
            """,
            (normalized_root,),
        ).fetchall()

        return {
            "tracked_files": tracked_files,
            "symbol_count": symbol_count,
            "import_count": import_count,
            "edge_count": edge_count,
            "languages": {row["language"]: int(row["count"]) for row in language_rows},
            "dependency_hubs": [
                {"import_text": row["import_text"], "count": int(row["count"])}
                for row in dependency_rows
            ],
            "refresh_run": refresh_run,
        }

    def clear_project(self, project_root: str) -> None:
        normalized_root = normalize_path(project_root)
        conn = self._get_conn()
        for table_name in ("file_manifest", "symbols", "imports", "edges", "refresh_runs"):
            conn.execute(f"DELETE FROM {table_name} WHERE project_root = ?", (normalized_root,))
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None