import lancedb
import pyarrow as pa
import re
import hashlib
import logging
import json
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from .config import LANCEDB_URI, TABLE_NAME, EMBEDDING_DIMENSIONS
from .models import CodeChunk
from .utils import normalize_path

logger = logging.getLogger(__name__)

def _sanitize_filter_value(value: str) -> str:
    """
    Escapes a string value for safe inclusion in LanceDB SQL-like filters.
    Doubles internal quotes.
    """
    if not isinstance(value, str):
        value = str(value)
    # Escape internal double quotes
    escaped = value.replace('"', '""')
    return escaped

class VectorStore:
    """Storage layer for code chunks using LanceDB with project-level isolation."""

    def __init__(self, uri: str = LANCEDB_URI):
        self.db = lancedb.connect(uri)
        self.embedding_dims = EMBEDDING_DIMENSIONS
        self._tables = {}
        self._lock = threading.Lock()

    def _get_table_name(self, project_root: str) -> str:
        """Generates a stable, unique table name for a given project root."""
        normalized_root = normalize_path(project_root)
        path_hash = hashlib.sha256(normalized_root.encode('utf-8')).hexdigest()[:32]
        return f"chunks_{path_hash}"

    def _get_metadata_table_name(self, project_root: str) -> str:
        """Generates a stable, unique table name for project metadata."""
        normalized_root = normalize_path(project_root)
        path_hash = hashlib.sha256(normalized_root.encode('utf-8')).hexdigest()[:32]
        return f"metadata_{path_hash}"

    def _get_table_or_none(self, project_root: str):
        """Helper to safely fetch a table or None if it doesn't exist."""
        table_name = self._get_table_name(project_root)
        
        with self._lock:
            # Check cache first
            if table_name in self._tables:
                return self._tables[table_name]
    
            # Robustly check for table existence
            try:
                all_tables = self.db.list_tables()
                if table_name not in all_tables:
                    # Final fallback check
                    if table_name not in self.db.table_names():
                        return None
            except Exception:
                try:
                    if table_name not in self.db.table_names():
                        return None
                except:
                    return None
                    
            try:
                table = self.db.open_table(table_name)
                self._tables[table_name] = table
                return table
            except Exception:
                return None

    def _ensure_table(self, table_name: str):
        """Creates the table if it doesn't exist."""
        with self._lock:
            if table_name in self._tables:
                return self._tables[table_name]
                
            try:
                all_tables = self.db.list_tables()
                if table_name not in all_tables:
                    self.db.create_table(table_name, schema=self._get_schema())
            except Exception as e:
                # If it already exists, just ignore and open it
                if "already exists" not in str(e).lower():
                    logger.error(f"Error checking/creating table {table_name}: {e}")
            
            try:
                table = self.db.open_table(table_name)
                self._tables[table_name] = table
                return table
            except Exception as e:
                logger.error(f"Failed to open table {table_name}: {e}")
                raise

    def clear_caches(self):
        """Resets the internal table handle cache."""
        self._tables = {}

    def _get_schema(self):
        """Returns the standard schema for code chunk tables."""
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("filename", pa.string()),
            pa.field("start_line", pa.int32()),
            pa.field("end_line", pa.int32()),
            pa.field("type", pa.string()),
            pa.field("language", pa.string()),
            pa.field("symbol_name", pa.string()),
            pa.field("parent_symbol", pa.string()),
            pa.field("signature", pa.string()),
            pa.field("docstring", pa.string()),
            pa.field("decorators", pa.string()),  # JSON-encoded list
            pa.field("last_modified", pa.string()),
            pa.field("author", pa.string()),
            pa.field("dependencies", pa.string()),  # JSON-encoded list
            pa.field("related_tests", pa.string()),  # JSON-encoded list
            pa.field("complexity", pa.int32()),
            pa.field("content", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), self.embedding_dims)),
        ])


    def upsert_chunks(self, project_root: str, chunks: List[CodeChunk], vectors: List[List[float]]):
        """Inserts or updates chunks into a project-specific table."""
        if not chunks:
            return

        table_name = self._get_table_name(project_root)
        table = self._ensure_table(table_name)
        
        # Prepare data for insertion
        data = []
        for chunk, vector in zip(chunks, vectors):
            data.append({
                "id": chunk.id,
                "filename": chunk.filename,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "type": chunk.type,
                "language": chunk.language,
                "symbol_name": chunk.symbol_name or "",
                "parent_symbol": chunk.parent_symbol or "",
                "signature": chunk.signature or "",
                "docstring": chunk.docstring or "",
                "decorators": json.dumps(chunk.decorators) if chunk.decorators else "",
                "last_modified": chunk.last_modified or "",
                "author": chunk.author or "",
                "dependencies": json.dumps(chunk.dependencies) if chunk.dependencies else "[]",
                "related_tests": json.dumps(chunk.related_tests) if chunk.related_tests else "[]",
                "complexity": chunk.complexity or 0,
                "content": chunk.content,
                "content_hash": chunk.content_hash or "",
                "vector": vector
            })
        
        # Delete existing entries for the file paths involved in this batch
        filepaths = list(set([c.filename for c in chunks]))
        for path in filepaths:
            safe_path = _sanitize_filter_value(path)
            table.delete(f'filename = "{safe_path}"')
            
        table.add(data)

    def search(self, project_root: str, query_vector: List[float], limit: int = 5) -> List[dict]:
        """Performs a semantic vector search within a specific project's table."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return []
            
        results = table.search(query_vector).limit(limit).to_list()
        return results

    def find_chunks_by_symbol(self, project_root: str, symbol_name: str) -> List[dict]:
        """Finds chunks with a specific symbol name (case-sensitive exact match)."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return []
        
        # LanceDB uses SQL-like filtering - sanitize input
        safe_name = _sanitize_filter_value(symbol_name)
        results = table.search().where(f'symbol_name = "{safe_name}"').to_list()
        return results

    def find_chunks_with_usage(self, project_root: str, symbol_name: str) -> List[dict]:
        """Finds chunks whose content references the target symbol name (used for external symbols)."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return []
        
        safe_name = _sanitize_filter_value(symbol_name)
        # LanceDB supports basic wildcard string matching with LIKE
        try:
            results = table.search().where(f'content LIKE "%{safe_name}%"').to_list()
            return results
        except Exception as e:
            logger.error(f"Fallback usage search failed: {e}")
            return []

    def find_chunks_containing_text(self, project_root: str, query_text: str, limit: int = 10) -> List[dict]:
        """Performs a literal textual search across chunk content (Keyword Fallback)."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return []
        
        safe_query = _sanitize_filter_value(query_text)
        try:
            # case-insensitive search if supported, otherwise LIKE match
            results = table.search().where(f'content LIKE "%{safe_query}%"').limit(limit).to_list()
            return results
        except Exception as e:
            logger.error(f"Keyword search failed for '{query_text}': {e}")
            return []

    def find_chunks_by_symbol_in_file(self, project_root: str, symbol_name: str, filepath: str) -> List[dict]:
        """Finds chunks with a specific symbol provided the filepath."""
        try:
            table = self._get_table_or_none(project_root)
            if table is None:
                return []
            
            safe_name = _sanitize_filter_value(symbol_name)
            safe_filepath = _sanitize_filter_value(normalize_path(filepath))
            
            results = table.search().where(f'symbol_name = "{safe_name}" AND filename = "{safe_filepath}"').to_list()
            return results
        except Exception as e:
            # logger.error(f"Error querying symbol in file: {e}")
            return []

    def get_chunk_by_id(self, project_root: str, chunk_id: str) -> Optional[dict]:
        """Retrieves a single chunk by its ID."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return None
        
        safe_id = _sanitize_filter_value(chunk_id)
        results = table.search().where(f'id = "{safe_id}"').to_list()
        return results[0] if results else None

    def clear_project(self, project_root: str):
        """Wipes the database table for a specific project."""
        table_name = self._get_table_name(project_root)
        try:
            # Pop Handle first to prevent stale writes/caching.
            self._tables.pop(table_name, None)
            
            # Use delete("1=1") first to be safe, then try to drop.
            # In some environments drop_table might be soft or delayed.
            try:
                table = self.db.open_table(table_name)
                table.delete("1=1")
            except:
                pass
                
            all_tables = self.db.list_tables()
            if table_name in all_tables:
                self.db.drop_table(table_name)
        except Exception as e:
            logger.warning(f"Failed to clear project {project_root}: {e}")

    def count_chunks(self, project_root: str) -> int:
        """Returns the total number of chunks for a project."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return 0
        
        return table.count_rows()

    def get_index_metadata(self, project_root: str) -> Optional[dict]:
        """Retrieves the index metadata for a project."""
        table_name = self._get_metadata_table_name(project_root)
        try:
            if table_name not in self.db.table_names():
                return None
            table = self.db.open_table(table_name)
            data = table.search().limit(1).to_list()
            return data[0] if data else None
        except Exception as e:
            # logger.warning(f"Failed to get index metadata: {e}")
            return None

    def save_index_metadata(self, project_root: str, metadata: dict):
        """Saves the index metadata for a project."""
        table_name = self._get_metadata_table_name(project_root)
        try:
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
                
            schema = pa.schema([
                pa.field("indexed_at", pa.string()),
                pa.field("commit_hash", pa.string()),
                pa.field("is_dirty", pa.bool_()),
                pa.field("scan_type", pa.string()),
                pa.field("model_name", pa.string())
            ])
            
            table = self.db.create_table(table_name, schema=schema)
            metadata["commit_hash"] = metadata.get("commit_hash") or ""
            table.add([metadata])
        except Exception as e:
            logger.error(f"Failed to save index metadata: {e}")

    def get_project_hashes(self, project_root: str) -> dict:
        """Returns a mapping of {filename: content_hash}."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return {}
        
        # We only need filename and content_hash
        try:
            # Check if column exists first (for legacy tables)
            schema = table.schema
            if "content_hash" not in schema.names:
                return {}

            data = table.search().select(["filename", "content_hash"]).to_arrow()
            if len(data) == 0:
                return {}
            
            # Map filename to content_hash using Arrow
            filenames = data.column("filename").to_pylist()
            hashes = data.column("content_hash").to_pylist()
            
            # We use a dict comprehension. If multiple chunks exist for one file, 
            # the last one's hash is used (they should be identical).
            return {f: h for f, h in zip(filenames, hashes) if h}
        except Exception as e:
            logger.warning(f"Failed to get project hashes: {e}")
            return {}

    def get_detailed_stats(self, project_root: str) -> dict:
        """Returns detailed architectural statistics for a project."""
        table = self._get_table_or_none(project_root)
        if table is None:
            return {}

        # Select ONLY the columns we need to process to avoid huge memory/time costs
        columns = ["filename", "language", "complexity", "symbol_name", "dependencies", "related_tests", "last_modified", "author", "end_line"]
        try:
            data = table.search().select(columns).to_arrow()
        except Exception as e:
             # Fallback for older LanceDB versions or different interfaces
             logger.warning(f"LanceDB search().select() failed, falling back to simple to_arrow(): {e}")
             data = table.to_arrow()
        
        if len(data) == 0:
            return {"chunk_count": 0}

        # Python-native aggregation over Arrow data
        filenames = data.column("filename").to_pylist()
        languages = data.column("language").to_pylist()
        complexities = data.column("complexity").to_pylist()
        symbol_names = data.column("symbol_name").to_pylist()
        end_lines = data.column("end_line").to_pylist()

        lang_counts = Counter(languages)
        unique_files = len(set(filenames))
        
        avg_comp = sum(complexities) / len(complexities) if complexities else 0
        max_comp = max(complexities) if complexities else 0

        # Architectural Metrics
        dependency_list = []
        for d in data.column("dependencies").to_pylist():
            try:
                dependency_list.extend(json.loads(d))
            except:
                pass
        
        dep_hubs = Counter(dependency_list).most_common(5)
        
        test_gaps = []
        stale_count: int = 0
        now = datetime.now(timezone.utc)
        
        for i in range(len(data)):
            # Test Gap check: complexity > 10 and no related tests
            try:
                rel_tests = json.loads(data.column("related_tests")[i].as_py() or "[]")
            except:
                rel_tests = []
            
            if complexities[i] > 10 and not rel_tests:
                test_gaps.append({
                    "symbol": symbol_names[i] or filenames[i],
                    "complexity": int(complexities[i]),
                    "file": filenames[i]
                })
 
            # Stale File check: modified > 30 days ago
            last_mod = data.column("last_modified")[i].as_py()
            if last_mod:
                try:
                    # Expected format: "2026-02-14 15:44:21 -0500"
                    # We'll take the first part
                    mod_date_str = last_mod.split(" ")[0]
                    mod_date = datetime.strptime(mod_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if (now - mod_date).days > 30:
                        stale_count += 1
                except:
                    pass

        # Identify high-risk symbols (top 5 by complexity)
        records = []
        file_max_lines = {}
        for i in range(len(data)):
            fname = filenames[i]
            eline = int(end_lines[i] or 0)
            if fname not in file_max_lines or eline > file_max_lines[fname]:
                file_max_lines[fname] = eline
                
            if complexities[i] > 0:
                records.append({
                    "symbol": symbol_names[i] or filenames[i],
                    "complexity": int(complexities[i]),
                    "file": filenames[i]
                })
        
        rule_violations = []
        for fname, max_line in file_max_lines.items():
            if max_line > 200:
                rule_violations.append({
                    "file": fname,
                    "lines": max_line,
                    "rule": "200/50 Rule: File exceeds 200 lines"
                })
        
        high_risk = sorted(records, key=lambda x: x["complexity"], reverse=True)[:5]
        test_gaps = sorted(test_gaps, key=lambda x: x["complexity"], reverse=True)[:5]

        return {
            "chunk_count": len(data),
            "file_count": unique_files,
            "languages": dict(lang_counts),
            "avg_complexity": float(avg_comp),
            "max_complexity": int(max_comp),
            "high_risk_symbols": high_risk,
            "dependency_hubs": [{"file": f, "count": c} for f, c in dep_hubs],
            "test_gaps": test_gaps,
            "stale_files_count": stale_count,
            "rule_violations": rule_violations
        }
