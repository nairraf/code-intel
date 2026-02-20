
import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server import refresh_index, find_references
from src.config import EMBEDDING_DIMENSIONS
from src.storage import VectorStore

@pytest.fixture
def mock_ollama():
    with patch("src.server.ollama_client") as mock:
        # Mock embeddings to simple deterministic vectors
        async def mock_emb(text):
            return [0.1] * EMBEDDING_DIMENSIONS
        
        async def mock_batch(texts, semaphore=None):
            return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]
            
        mock.get_embedding = AsyncMock(side_effect=mock_emb)
        mock.get_embeddings_batch = AsyncMock(side_effect=mock_batch)
        yield mock

@pytest.fixture
def mock_vector_store():
    # Use real VectorStore but with temp DB path handling?
    # Or mock it if we trust logic? 
    # Integration tests usually benefit from real components with temp DB.
    # Let's use patch to redirect storage to a temp dir.
    pass

@pytest.mark.asyncio
async def test_two_pass_linking_high_confidence(tmp_path, mock_ollama):
    """
    Verifies that a symbol defined in one file and used in another
    is correctly linked with High Confidence (explicit import).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # 1. Setup Files
    # Definition
    (project_root / "service.py").write_text("class MyService:\n    def do_work(self):\n        pass", encoding="utf-8")
    
    # Usage (Explicit Import)
    (project_root / "app.py").write_text("from service import MyService\n\ndef main():\n    s = MyService()\n    s.do_work()", encoding="utf-8")
    
    # 2. Patch VectorStore config to use tmp_path
    # We can't easily patch the DB URI globally if it's already initialized in server.py
    # So we patch the global 'vector_store' instance in server.py with a new one rooted at tmp_path
    from src.storage import VectorStore
    
    # Create a fresh store for this test
    test_store = VectorStore(uri=str(tmp_path / "lancedb"))
    
    with patch("src.server.vector_store", test_store), \
         patch("src.server.linker.vector_store", test_store):
        # 3. Run Indexing (Two-Pass should happen here)
        result = await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        assert "Indexing Complete" in result
        
        # 4. Verify References
        refs = await find_references.fn(symbol_name="MyService", root_path=str(project_root))
        
        print(f"DEBUG REFS: {refs}")
        
        assert "Referenced in" in refs
        assert "app.py" in refs
        assert "High Confidence: explicit_import" in refs

@pytest.mark.asyncio
async def test_two_pass_linking_low_confidence(tmp_path, mock_ollama):
    """
    Verifies that a symbol used WITHOUT explicit import (or dynamic/wildcard)
    is linked with Low Confidence (name match).
    """
    project_root = tmp_path / "project_low"
    project_root.mkdir()
    
    # 1. Setup Files
    # Definition
    (project_root / "utils.py").write_text("def helper(): pass", encoding="utf-8")
    
    # Usage (No import - maybe dynamic or just missing, but same name)
    # Note: If parser doesn't see import, it won't resolve.
    (project_root / "script.py").write_text("# no import\ndef main():\n    helper()", encoding="utf-8")
    
    test_store = VectorStore(uri=str(tmp_path / "lancedb_low"))
    
    with patch("src.server.vector_store", test_store), \
         patch("src.server.linker.vector_store", test_store):
        await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        
        refs = await find_references.fn(symbol_name="helper", root_path=str(project_root))
        
        # Should be found via global fallback
        assert "Referenced in" in refs
        assert "script.py" in refs
        assert "Low Confidence: name_match" in refs

