import sqlite3
import pickle
import logging
import hashlib
from datetime import datetime
from typing import List, Optional
from .config import CACHE_DB_PATH

logger = logging.getLogger(__name__)

class EmbeddingCache:
    """
    Local SQLite cache for embeddings to reduce latency and Ollama usage.
    Schema: (hash TEXT PRIMARY KEY, vector BLOB, model TEXT, created_at TIMESTAMP, last_accessed TIMESTAMP)
    """

    def __init__(self, db_path: str = str(CACHE_DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Ensures the cache table exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        hash TEXT PRIMARY KEY,
                        vector BLOB,
                        model TEXT,
                        created_at TIMESTAMP,
                        last_accessed TIMESTAMP
                    )
                """)
                # Index for model to allow potential filtering/pruning by model type
                conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON embeddings(model)")
                # Index for last_accessed for LRU pruning
                conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON embeddings(last_accessed)")
        except Exception as e:
            logger.error(f"Failed to initialize embedding cache at {self.db_path}: {e}")

    def _compute_hash(self, text: str, model: str) -> str:
        """Computes a deterministic hash for the text and model combination."""
        # We hash both text and model so that if we switch embedding models, 
        # we don't return invalid vectors.
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, text: str, model: str) -> Optional[List[float]]:
        """Retrieves an embedding from the cache if it exists."""
        text_hash = self._compute_hash(text, model)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT vector FROM embeddings WHERE hash = ?", 
                        (text_hash,)
                    )
                except sqlite3.OperationalError as e:
                    if "no such table: embeddings" in str(e):
                        logger.info("Cache table missing, initializing...")
                        self._init_db()
                        return None # Miss this time, next time it will work
                    raise
                
                row = cursor.fetchone()
                
                if row:
                    # Update last_accessed
                    conn.execute(
                        "UPDATE embeddings SET last_accessed = ? WHERE hash = ?",
                        (datetime.utcnow(), text_hash)
                    )
                    return pickle.loads(row[0])
        except Exception as e:
            logger.warning(f"Cache read failed for {text_hash}: {e}")
        
        return None

    def set(self, text: str, model: str, vector: List[float]):
        """Stores an embedding in the cache."""
        text_hash = self._compute_hash(text, model)
        try:
            blob = pickle.dumps(vector)
            now = datetime.utcnow()
            with sqlite3.connect(self.db_path) as conn:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO embeddings (hash, vector, model, created_at, last_accessed)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (text_hash, blob, model, now, now)
                    )
                except sqlite3.OperationalError as e:
                    if "no such table: embeddings" in str(e):
                        logger.info("Cache table missing during write, initializing...")
                        self._init_db()
                        # Retry once
                        with sqlite3.connect(self.db_path) as conn2:
                            conn2.execute(
                                """
                                INSERT OR REPLACE INTO embeddings (hash, vector, model, created_at, last_accessed)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (text_hash, blob, model, now, now)
                            )
                        return
                    raise
        except Exception as e:
            logger.error(f"Cache write failed for {text_hash}: {e}")

    def prune(self, days: int = 30):
        """Removes entries not accessed in the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM embeddings WHERE last_accessed < datetime('now', ?)",
                    (f'-{days} days',)
                )
                logger.info(f"Pruned cache entries older than {days} days.")
        except Exception as e:
            logger.error(f"Cache pruning failed: {e}")
