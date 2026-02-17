import lancedb
import pyarrow as pa
import hashlib
from typing import List, Optional
from pathlib import Path
from .config import LANCEDB_URI, TABLE_NAME, EMBEDDING_DIMENSIONS
from .models import CodeChunk

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
