import pytest
import os
import sys
import shutil
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server import refresh_index, search_code, get_stats
from src.config import EMBEDDING_DIMENSIONS


@pytest.fixture
def dummy_project(tmp_path):
    """Creates a small project with a few files."""
    project_root = tmp_path / "integration_proj"
    project_root.mkdir()
    
    (project_root / "main.py").write_text("""
def hello():
    \"\"\"This is a test function.\"\"\"
    print("Hello World")

class Greeter:
    def __init__(self):
        pass
    def greet(self):
        hello()
""")
    
    (project_root / "utils.py").write_text("""
def add(a, b):
    return a + b
""")
    
    (project_root / "styles.css").write_text(".body { color: red; }")
    
    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)

@pytest.mark.asyncio
async def test_end_to_end_flow(dummy_project, tmp_path):
    # Use a temp lancedb for this integration test
    temp_db_uri = tmp_path / "integration_lancedb"
    
    # We need to patch the global instances in src.server
    with patch("src.server.ollama_client") as mock_ollama, \
         patch("src.server.vector_store") as mock_store_dummy, \
         patch("src.server.LOG_DIR", tmp_path): # Prevents log pollution
        
        # Actually, we want a REAL VectorStore but pointed at our temp DB
        from src.storage import VectorStore
        real_store = VectorStore(uri=str(temp_db_uri))
        
        # Replace the server.vector_store with our real_store pointed at temp DB
        with patch("src.server.vector_store", real_store):
            
            # Mock Ollama to return deterministic vectors based on text length
            # to make search results predictable
            async def mock_get_embedding(text):
                return [float(len(text))] * EMBEDDING_DIMENSIONS
            
            async def mock_get_embeddings_batch(texts, **kwargs):
                return [[float(len(t))] * EMBEDDING_DIMENSIONS for t in texts]
                
            mock_ollama.get_embedding = AsyncMock(side_effect=mock_get_embedding)
            mock_ollama.get_embeddings_batch = AsyncMock(side_effect=mock_get_embeddings_batch)

            
            # 1. Run Refresh Index
            refresh_result = await refresh_index.fn(root_path=str(dummy_project))
            assert "Indexing Complete" in refresh_result
            assert "Files Scanned: 3" in refresh_result # main.py, utils.py, styles.css
            
            # 2. Run Search Code
            # "hello" has length 5. Search for it.
            search_result = await search_code.fn(query="hello", root_path=str(dummy_project))
            assert "main.py" in search_result
            assert "def hello():" in search_result
            
            # 3. Get Stats
            stats_result = await get_stats.fn(root_path=str(dummy_project))
            assert "Total Chunks:" in stats_result
            assert "Unique Files:     3" in stats_result
            assert "python: " in stats_result
            
            # 4. Incremental update check (add a new file)
            (dummy_project / "new.py").write_text("def extra(): pass")
            refresh_result_inc = await refresh_index.fn(root_path=str(dummy_project))
            assert "Incremental Update" in refresh_result_inc
            assert "Files Scanned: 4 (3 skipped)" in refresh_result_inc
            
            # 5. Search for the new symbol
            search_result_new = await search_code.fn(query="extra", root_path=str(dummy_project))
            assert "new.py" in search_result_new
            assert "def extra()" in search_result_new
