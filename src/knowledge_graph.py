import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from .config import CACHE_DIR

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    Manages the 'edges' table in SQLite to store relationships between code chunks.
    Relationships include:
    - 'import': Source chunk imports Target chunk
    - 'call': Source chunk calls Target chunk
    - 'inheritance': Source chunk inherits from Target chunk
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(CACHE_DIR / "knowledge_graph.sqlite")
        self.db_path = db_path
        self._conn = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    project_root TEXT,
                    source_chunk_id TEXT,
                    target_chunk_id TEXT,
                    type TEXT,
                    metadata TEXT,
                    source_filename TEXT,
                    target_filename TEXT,
                    PRIMARY KEY (source_chunk_id, target_chunk_id, type)
                )
            """)
            existing_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(edges)").fetchall()
            }
            if "project_root" not in existing_columns:
                conn.execute("ALTER TABLE edges ADD COLUMN project_root TEXT")
            if "source_filename" not in existing_columns:
                conn.execute("ALTER TABLE edges ADD COLUMN source_filename TEXT")
            if "target_filename" not in existing_columns:
                conn.execute("ALTER TABLE edges ADD COLUMN target_filename TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON edges(source_chunk_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON edges(target_chunk_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project_root ON edges(project_root)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_filename ON edges(source_filename)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_target_filename ON edges(target_filename)")
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize knowledge graph at {self.db_path}: {e}")

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        type: str,
        metadata: Dict = None,
        auto_commit: bool = True,
        project_root: Optional[str] = None,
        source_filename: Optional[str] = None,
        target_filename: Optional[str] = None,
    ):
        """Adds a relationship edge."""
        try:
            meta_json = json.dumps(metadata) if metadata else "{}"
            conn = self._get_conn()
            conn.execute(
                """
                INSERT OR REPLACE INTO edges (
                    project_root,
                    source_chunk_id,
                    target_chunk_id,
                    type,
                    metadata,
                    source_filename,
                    target_filename
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_root,
                    source_id,
                    target_id,
                    type,
                    meta_json,
                    source_filename,
                    target_filename,
                )
            )
            if auto_commit:
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to add edge {source_id} -> {target_id}: {e}")

    def begin_transaction(self):
        """Starts a manual transaction."""
        try:
            conn = self._get_conn()
            conn.execute("BEGIN TRANSACTION")
        except Exception as e:
            logger.error(f"Failed to begin transaction: {e}")

    def commit_transaction(self):
        """Commits a manual transaction."""
        try:
            conn = self._get_conn()
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to commit transaction: {e}")

    def get_edges(
        self,
        source_id: str = None,
        target_id: str = None,
        type: str = None,
        project_root: str = None,
    ) -> List[Tuple[str, str, str, Dict]]:
        """
        Retrieves edges matching criteria.
        Returns list of (source_id, target_id, type, metadata_dict).
        """
        query = "SELECT source_chunk_id, target_chunk_id, type, metadata FROM edges WHERE 1=1"
        params = []
        
        if source_id:
            query += " AND source_chunk_id = ?"
            params.append(source_id)
        if target_id:
            query += " AND target_chunk_id = ?"
            params.append(target_id)
        if type:
            query += " AND type = ?"
            params.append(type)
        if project_root:
            query += " AND project_root = ?"
            params.append(project_root)
            
        try:
            conn = self._get_conn()
            cursor = conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                s_id, t_id, t_type, meta_json = row
                meta = json.loads(meta_json) if meta_json else {}
                results.append((s_id, t_id, t_type, meta))
            return results
        except Exception as e:
            logger.error(f"Failed to query edges: {e}")
            return []

    def get_source_files(self, project_root: str, target_filenames: List[str]) -> List[str]:
        """Returns distinct source files with edges pointing at the given target files."""
        if not target_filenames:
            return []

        placeholders = ", ".join("?" for _ in target_filenames)
        query = (
            "SELECT DISTINCT source_filename FROM edges "
            "WHERE project_root = ? AND target_filename IN (" + placeholders + ")"
        )
        params = [project_root, *target_filenames]

        try:
            conn = self._get_conn()
            cursor = conn.execute(query, params)
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception as e:
            logger.error(f"Failed to query source files for project {project_root}: {e}")
            return []

    def delete_file_edges(self, project_root: str, filenames: List[str], auto_commit: bool = True):
        """Deletes edges where the source or target belongs to any of the given files."""
        if not filenames:
            return

        placeholders = ", ".join("?" for _ in filenames)
        query = (
            "DELETE FROM edges WHERE project_root = ? AND ("
            f"source_filename IN ({placeholders}) OR target_filename IN ({placeholders})"
            ")"
        )
        params = [project_root, *filenames, *filenames]

        try:
            conn = self._get_conn()
            conn.execute(query, params)
            if auto_commit:
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete file edges for project {project_root}: {e}")

    def clear(self, auto_commit: bool = True):
        """Clears all edges."""
        try:
            conn = self._get_conn()
            conn.execute("DELETE FROM edges")
            if auto_commit:
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear knowledge graph: {e}")

    def clear_project(self, project_root: str, auto_commit: bool = True):
        """Clears all edges for a specific project."""
        try:
            conn = self._get_conn()
            conn.execute("DELETE FROM edges WHERE project_root = ?", (project_root,))
            if auto_commit:
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear knowledge graph for project {project_root}: {e}")

    def close(self):
        """Closes the persistent database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
