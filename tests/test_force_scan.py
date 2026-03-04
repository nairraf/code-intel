import pytest
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, AsyncMock, patch
from src.storage import VectorStore
from src.server import refresh_index as refresh_index_tool
from src.config import EMBEDDING_DIMENSIONS


@pytest.mark.asyncio
async def test_force_full_scan():
    with patch('src.context._context.vector_store') as mock_store, \
         patch('src.context._context.ollama') as mock_ollama, \
         patch('src.context._context.parser') as mock_parser, \
         patch('src.indexer.os.walk') as mock_walk, \
         patch('src.indexer.batch_get_git_info', new_callable=AsyncMock) as mock_git:

        mock_git.return_value = {}
        mock_store.count_chunks.side_effect = [5, 10]
        mock_store.clear_project = MagicMock()
        mock_store.upsert_chunks = MagicMock()

        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1] * EMBEDDING_DIMENSIONS])

        from src.models import CodeChunk
        mock_parser.parse_file.return_value = [CodeChunk(
            id="test-id", filename="test.py", start_line=1, end_line=10,
            content="print('hello')", type="function", language="python",
            symbol_name="mock_func", parent_symbol=None, signature=None,
            docstring=None, decorators=None, last_modified=None, author=None
        )]

        mock_walk.return_value = [("/root", [], ["test.py"])]

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)), \
             patch('builtins.open', new_callable=MagicMock):

            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=True)

            mock_store.clear_project.assert_called_once()
            assert "Full Rebuild" in result
            assert "Total Chunks in Index: 10" in result


@pytest.mark.asyncio
async def test_incremental_scan():
    with patch('src.context._context.vector_store') as mock_store, \
         patch('src.context._context.ollama') as mock_ollama, \
         patch('src.context._context.parser') as mock_parser, \
         patch('src.indexer.os.walk') as mock_walk, \
         patch('src.indexer.batch_get_git_info', new_callable=AsyncMock) as mock_git:

        mock_git.return_value = {}
        mock_store.count_chunks.side_effect = [10, 12]
        mock_store.clear_project = MagicMock()
        mock_store.upsert_chunks = MagicMock()

        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1] * EMBEDDING_DIMENSIONS])

        from src.models import CodeChunk
        mock_parser.parse_file.return_value = [CodeChunk(
            id="test-id", filename="test.py", start_line=1, end_line=10,
            content="print('hello')", type="function", language="python"
        )]

        mock_walk.return_value = [("/root", [], ["test.py"])]

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)), \
             patch('builtins.open', new_callable=MagicMock):

            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=False)

            mock_store.clear_project.assert_not_called()
            assert "Incremental Update" in result
            assert "Total Chunks in Index: 12" in result
