import pytest
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, AsyncMock, patch
from src.storage import VectorStore
from src.server import refresh_index as refresh_index_tool

@pytest.mark.asyncio
async def test_force_full_scan():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store, \
         patch('src.server.ollama_client') as mock_ollama, \
         patch('src.server.parser') as mock_parser, \
         patch('src.server.os.walk') as mock_walk, \
         patch('src.server.batch_get_git_info', new_callable=AsyncMock) as mock_git:
        
        # Setup mocks
        mock_git.return_value = {}
        mock_store.count_chunks.side_effect = [5, 10] # Initial count 5, final count 10
        mock_store.clear_project = MagicMock()
        mock_store.upsert_chunks = MagicMock()
        
        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1]*1024])
        
        # Mock parsing a single file
        from src.models import CodeChunk
        mock_parser.parse_file.return_value = [CodeChunk(
            id="test-id", filename="test.py", start_line=1, end_line=10,
            content="print('hello')", type="function", language="python",
            symbol_name="mock_func", parent_symbol=None, signature=None, docstring=None, decorators=None, last_modified=None, author=None
        )]
        
        # Mock file system walk
        mock_walk.return_value = [("/root", [], ["test.py"])]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)), \
             patch('builtins.open', new_callable=MagicMock):
            
            # Run tool with force_full_scan=True
            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=True)
            
            # Verify clear_project was called
            mock_store.clear_project.assert_called_once()
            
            # Verify stats in output
            assert "Full Rebuild" in result
            assert "Total Chunks in Index: 10" in result
            assert "Delta: 5" in result

@pytest.mark.asyncio
async def test_incremental_scan():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store, \
         patch('src.server.ollama_client') as mock_ollama, \
         patch('src.server.parser') as mock_parser, \
         patch('src.server.os.walk') as mock_walk, \
         patch('src.server.batch_get_git_info', new_callable=AsyncMock) as mock_git:
        
        # Setup mocks
        mock_git.return_value = {}
        mock_store.count_chunks.side_effect = [10, 12] 
        mock_store.clear_project = MagicMock()
        mock_store.upsert_chunks = MagicMock()
        
        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1]*1024])
        
        from src.models import CodeChunk
        mock_parser.parse_file.return_value = [CodeChunk(
            id="test-id", filename="test.py", start_line=1, end_line=10, 
            content="print('hello')", type="function", language="python"
        )]
        
        mock_walk.return_value = [("/root", [], ["test.py"])]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)), \
             patch('builtins.open', new_callable=MagicMock):
            
            # Run tool with force_full_scan=False (Default)
            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=False)
            
            # Verify clear_project was NOT called
            mock_store.clear_project.assert_not_called()
            
            # Verify stats in output
            assert "Incremental Update" in result
            assert "Total Chunks in Index: 12" in result
            assert "Delta: 2" in result
