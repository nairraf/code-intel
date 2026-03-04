import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, AsyncMock, patch
from src.storage import VectorStore
from src.tools.stats import get_stats_impl


@pytest.mark.asyncio
async def test_get_stats_active():
    mock_ctx = MagicMock()
    mock_ctx.vector_store.get_detailed_stats.return_value = {
        "chunk_count": 42,
        "file_count": 5,
        "languages": {"python": 42},
        "avg_complexity": 3.5,
        "max_complexity": 10,
        "high_risk_symbols": [],
        "dependency_hubs": [],
        "test_gaps": [],
        "stale_files_count": 0
    }

    with patch('src.tools.stats.get_active_branch', return_value="main"):
        result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

        assert "Total Chunks:     42" in result
        assert "Stats for:" in result
        assert "Active Branch: main" in result
        assert "Project Pulse:" in result


@pytest.mark.asyncio
async def test_get_stats_empty():
    mock_ctx = MagicMock()
    mock_ctx.vector_store.get_detailed_stats.return_value = {}

    result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

    assert "No index found for project" in result
