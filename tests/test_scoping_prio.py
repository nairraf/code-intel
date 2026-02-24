import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, patch
from src.server import _get_file_priority, _find_definition, refresh_index
from src.storage import VectorStore
from src.config import EMBEDDING_DIMENSIONS

def test_file_priority_logic():
    """Tests the weighting of file types."""
    assert _get_file_priority("main.py") == 100
    assert _get_file_priority("app.dart") == 100
    assert _get_file_priority("README.md") == 50
    assert _get_file_priority("data.json") == 10
    assert _get_file_priority("archive.zip") == 10

@pytest.mark.asyncio
async def test_artifact_filtering(tmp_path):
    """Verifies that the brain/ directory is ignored during indexing."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # 1. Setup Source and Brain files
    (project_root / "main.py").write_text("def foo(): pass", encoding="utf-8")
    brain_dir = project_root / "brain"
    brain_dir.mkdir()
    (brain_dir / "security_report.md").write_text("# Security Report\nFound foo in main.py", encoding="utf-8")
    
    # 2. Mock vector store and ollama
    test_store = VectorStore(uri=str(tmp_path / "lancedb_filter"))
    
    # We must be careful to mock attributes that refresh_index_impl uses
    with patch("src.server.vector_store", test_store), \
         patch("src.server.ollama_client") as mock_ollama, \
         patch("src.server.parser") as mock_parser:
        
        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1]*EMBEDDING_DIMENSIONS])
        
        # refresh_index_impl checks parser.ext_map (via _get_language or directly)
        mock_parser.ext_map = {".py": "python"}
        # Provide real parsers if needed or mock them
        mock_parser.parsers = {} 
        
        from src.models import CodeChunk
        mock_parser.parse_file.return_value = [CodeChunk(
            id="test", filename=str(project_root / "main.py"), start_line=1, end_line=1, 
            content="def foo(): pass", language="python", symbol_name="foo", type="function"
        )]
        
        # Run Indexing
        await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        
        # Check chunks in DB via table scan
        table = test_store.db.open_table(test_store._get_table_name(str(project_root)))
        results = table.to_arrow().to_pylist()
        
        filenames = [r["filename"] for r in results]
        assert any("main.py" in f for f in filenames)
        assert not any("brain" in f for f in filenames)

@pytest.mark.asyncio
async def test_language_scoped_definition(tmp_path):
    """Verifies that definition jumps prioritized by source language."""
    project_root = tmp_path / "project_scoped"
    project_root.mkdir()
    
    py_file = project_root / "config.py"
    py_file.write_text("class Settings: pass", encoding="utf-8")
    dart_file = project_root / "main.dart"
    dart_file.write_text("// ProviderScope usage", encoding="utf-8")
    
    test_store = VectorStore(uri=str(tmp_path / "lancedb_scoped"))
    
    # Prepare mock chunks for DB
    dart_dc = {
        "id": "dart_settings",
        "filename": str(dart_file),
        "start_line": 1,
        "end_line": 1,
        "content": "class Settings {}",
        "language": "dart",
        "symbol_name": "Settings",
        "type": "class"
    }
    py_dc = {
        "id": "py_settings",
        "filename": str(py_file),
        "start_line": 1,
        "end_line": 1,
        "content": "class Settings: pass",
        "language": "python",
        "symbol_name": "Settings",
        "type": "class"
    }
    
    # Mock find_chunks_by_symbol to return both
    def mock_find(root, name):
        if name == "Settings":
            # Return BOTH to test prioritization/filtering
            return [dart_dc, py_dc]
        return []

    with patch("src.server.vector_store") as mock_store, \
         patch("src.server.parser") as mock_parser:
        
        mock_store.find_chunks_by_symbol.side_effect = mock_find
        
        # Mock _get_language to tell server which language the CURRENT file is
        def mock_get_lang(f):
            f_str = str(f)
            if f_str.endswith(".py"): return "python"
            if f_str.endswith(".dart"): return "dart"
            return "unknown"
            
        mock_parser._get_language.side_effect = mock_get_lang
        mock_parser.parse_file.return_value = [] # Fail AST resolution -> triggers fallback search
        
        # 1. From Python file
        result_py = await _find_definition(str(py_file), 1, "Settings", root_path=str(project_root))
        # The first candidate in the string should be the Python one
        first_line = result_py.split("\n")[0]
        assert "config.py" in first_line
        
        # 2. From Dart file
        result_dart = await _find_definition(str(dart_file), 1, "Settings", root_path=str(project_root))
        # The first candidate in the string should be the Dart one
        first_line = result_dart.split("\n")[0]
        assert "main.dart" in first_line
