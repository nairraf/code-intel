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
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS edges (
                        source_chunk_id TEXT,
                        target_chunk_id TEXT,
                        type TEXT,
                        metadata TEXT,
                        PRIMARY KEY (source_chunk_id, target_chunk_id, type)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON edges(source_chunk_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON edges(target_chunk_id)")
        except Exception as e:
            logger.error(f"Failed to initialize knowledge graph at {self.db_path}: {e}")

    def add_edge(self, source_id: str, target_id: str, type: str, metadata: Dict = None):
        """Adds a relationship edge."""
        try:
            meta_json = json.dumps(metadata) if metadata else "{}"
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO edges (source_chunk_id, target_chunk_id, type, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (source_id, target_id, type, meta_json)
                )
        except Exception as e:
            logger.error(f"Failed to add edge {source_id} -> {target_id}: {e}")

    def get_edges(self, source_id: str = None, target_id: str = None, type: str = None) -> List[Tuple[str, str, str, Dict]]:
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
            
        try:
            with sqlite3.connect(self.db_path) as conn:
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

    def clear(self):
        """Clears all edges."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM edges")
        except Exception as e:
            logger.error(f"Failed to clear knowledge graph: {e}")
