import lancedb
import pyarrow as pa
import hashlib
import logging
from typing import List, Optional
from pathlib import Path
from .config import LANCEDB_URI, TABLE_NAME, EMBEDDING_DIMENSIONS
from .models import CodeChunk

logger = logging.getLogger(__name__)

class VectorStore:
    """Storage layer for code chunks using LanceDB with project-level isolation."""

    def __init__(self, uri: str = LANCEDB_URI):
        self.db = lancedb.connect(uri)
        self.embedding_dims = EMBEDDING_DIMENSIONS

    def _get_table_name(self, project_root: str) -> str:
        """Generates a stable, unique table name for a given project root."""
        abs_path = str(Path(project_root).resolve())
        path_hash = hashlib.md5(abs_path.encode('utf-8')).hexdigest()
        return f"chunks_{path_hash}"

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
            pa.field("vector", pa.list_(pa.float32(), self.embedding_dims)),
        ])

    def _ensure_table(self, table_name: str):
        """Creates the table if it doesn't exist."""
        if table_name not in self.db.table_names():
            self.db.create_table(table_name, schema=self._get_schema())
        return self.db.open_table(table_name)

    def upsert_chunks(self, project_root: str, chunks: List[CodeChunk], vectors: List[List[float]]):
        """Inserts or updates chunks into a project-specific table."""
        if not chunks:
            return

        table_name = self._get_table_name(project_root)
        table = self._ensure_table(table_name)
        
        import json
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
                "vector": vector
            })
        
        # Delete existing entries for the file paths involved in this batch
        filepaths = list(set([c.filename for c in chunks]))
        for path in filepaths:
            # Note: filter strings must be escaped if paths contain special chars
            safe_path = path.replace('"', '""')
            table.delete(f'filename = "{safe_path}"')
            
        table.add(data)

    def search(self, project_root: str, query_vector: List[float], limit: int = 5) -> List[dict]:
        """Performs a semantic vector search within a specific project's table."""
        table_name = self._get_table_name(project_root)
        
        if table_name not in self.db.table_names():
            return []
            
        table = self.db.open_table(table_name)
        results = table.search(query_vector).limit(limit).to_list()
        return results

    def clear_project(self, project_root: str):
        """Wipes the database table for a specific project."""
        table_name = self._get_table_name(project_root)
        if table_name in self.db.table_names():
            self.db.drop_table(table_name)

    def count_chunks(self, project_root: str) -> int:
        """Returns the total number of chunks for a project."""
        table_name = self._get_table_name(project_root)
        if table_name not in self.db.table_names():
            return 0
        
        table = self.db.open_table(table_name)
        return table.count_rows()

    def get_detailed_stats(self, project_root: str) -> dict:
        """Returns detailed architectural statistics for a project."""
        table_name = self._get_table_name(project_root)
        
        # Robustly check for table existence (handling different LanceDB return types)
        try:
            all_tables = self.db.list_tables()
            if not isinstance(all_tables, list):
                # Handle object with .tables attribute
                all_tables = getattr(all_tables, "tables", [])
            
            if table_name not in all_tables:
                return {}
        except Exception:
            return {}

        table = self.db.open_table(table_name)
        # Select ONLY the columns we need to process to avoid huge memory/time costs
        columns = ["filename", "language", "complexity", "symbol_name", "dependencies", "related_tests", "last_modified", "author"]
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

        from collections import Counter
        from datetime import datetime, timezone
        import json

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
        stale_count = 0
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
        for i in range(len(data)):
            if complexities[i] > 0:
                records.append({
                    "symbol": symbol_names[i] or filenames[i],
                    "complexity": int(complexities[i]),
                    "file": filenames[i]
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
            "stale_files_count": stale_count
        }
