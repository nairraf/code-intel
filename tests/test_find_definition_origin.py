import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server import refresh_index, find_definition
from src.config import EMBEDDING_DIMENSIONS
from src.storage import VectorStore
from src.knowledge_graph import KnowledgeGraph

@pytest.fixture
def mock_ollama():
    with patch("src.server.ollama_client") as mock:
        async def mock_emb(text):
            return [0.1] * EMBEDDING_DIMENSIONS
        
        async def mock_batch(texts, semaphore=None):
            return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]
            
        mock.get_embedding = AsyncMock(side_effect=mock_emb)
        mock.get_embeddings_batch = AsyncMock(side_effect=mock_batch)
        yield mock

@pytest.mark.asyncio
async def test_find_definition_ast_origin(tmp_path, mock_ollama):
    """
    Verifies that find_definition correctly resolves the origin of a dependency injection
    or function call using the filename and line number via AST mapping.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # 1. Setup Files
    # Definition
    (project_root / "auth.py").write_text("def verify_token():\n    return True\n", encoding="utf-8")
    
    # Usage
    (project_root / "main.py").write_text("from auth import verify_token\n\ndef route(token=Depends(verify_token)):\n    pass\n", encoding="utf-8")
    
    test_store = VectorStore(uri=str(tmp_path / "lancedb"))
    test_graph = KnowledgeGraph(db_path=str(tmp_path / "kg.sqlite"))
    
    with patch("src.server.vector_store", test_store), \
         patch("src.server.knowledge_graph", test_graph), \
         patch("src.server.linker.vector_store", test_store), \
         patch("src.server.linker.knowledge_graph", test_graph):
         
        # Run Indexing
        await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        
        # Test find_definition using filename and line
        # In main.py, verify_token is used on line 3 (def route(token=Depends(verify_token)):)
        main_py_path = str(project_root / "main.py")
        
        res = await find_definition.fn(filename=main_py_path, line=3, symbol_name="verify_token", root_path=str(project_root))
        
        assert "auth.py" in res
        assert "def verify_token():" in res

@pytest.mark.asyncio
async def test_find_definition_fallback(tmp_path, mock_ollama):
    """
    Verifies that find_definition falls back to global symbol search if AST mapping fails.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    (project_root / "utils.py").write_text("def my_helper():\n    pass\n", encoding="utf-8")
    
    test_store = VectorStore(uri=str(tmp_path / "lancedb"))
    test_graph = KnowledgeGraph(db_path=str(tmp_path / "kg.sqlite"))
    
    with patch("src.server.vector_store", test_store), \
         patch("src.server.knowledge_graph", test_graph), \
         patch("src.server.linker.vector_store", test_store), \
         patch("src.server.linker.knowledge_graph", test_graph):
         
        await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        
        # Pass a bogus file/line but correct symbol
        res = await find_definition.fn(filename="bogus.py", line=99, symbol_name="my_helper", root_path=str(project_root))
        
        assert "utils.py" in res
        assert "def my_helper():" in res
