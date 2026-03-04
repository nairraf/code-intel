import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from src.server import refresh_index, search_code
from src.config import EMBEDDING_DIMENSIONS


@pytest.mark.asyncio
async def test_refresh_index_flow(mocker):
    project_root = Path("temp_proj_sys")
    project_root.mkdir(exist_ok=True)
    (project_root / "file1.py").write_text("def test(): pass")

    try:
        mock_vec_store = mocker.patch("src.context._context.vector_store")
        mock_ollama = mocker.patch("src.context._context.ollama")
        mocker.patch("src.indexer.batch_get_git_info", new_callable=AsyncMock, return_value={})

        mock_ollama.get_embeddings_batch = AsyncMock(return_value=[[0.1] * EMBEDDING_DIMENSIONS])

        result = await refresh_index.fn(str(project_root))

        assert "Indexing Complete" in result
        assert "Files Scanned: 1" in result
        mock_vec_store.upsert_chunks.assert_called()
    finally:
        if project_root.exists():
            shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_search_code_flow(mocker):
    mock_vec_store = mocker.patch("src.context._context.vector_store")
    mock_ollama = mocker.patch("src.context._context.ollama")

    mock_ollama.get_embedding = AsyncMock(return_value=[0.1] * EMBEDDING_DIMENSIONS)

    mock_vec_store.search.return_value = [
        {
            "filename": "test.py",
            "start_line": 1,
            "end_line": 5,
            "type": "function_definition",
            "content": "def mock_func(): pass",
            "_distance": 0.05,
            "symbol_name": "mock_func",
            "parent_symbol": None,
            "signature": "mock_func()",
            "docstring": "A mock function.",
            "decorators": None,
            "last_modified": "2026-02-16 12:00:00",
            "author": "Test Author",
            "language": "python",
        }
    ]
    result = await search_code.fn("my query", root_path="fake_project")
    assert "Results for project" in result
    assert "test.py" in result
    assert "mock_func" in result
    assert "Author: Test Author" in result
    assert "Date: 2026-02-16 12:00:00" in result


@pytest.mark.asyncio
async def test_refresh_index_missing_path():
    result = await refresh_index.fn("non_existent_path_xyz")
    assert "Error: Path" in result
    assert "does not exist" in result
