import pytest
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, AsyncMock, patch
from src.storage import VectorStore
from src.server import get_stats_impl

@pytest.mark.asyncio
async def test_get_stats_active():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store:
        
        # Setup mocks
        mock_store.get_detailed_stats.return_value = {
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
        
        with patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=lambda x: str(x))), \
             patch('src.git_utils.get_active_branch', return_value="main"):
            
            # Run tool
            result = await get_stats_impl(root_path="/root")
            
            # Verify stats in output
            assert "Total Chunks:     42" in result
            assert "Status:           Active" in result
            assert "Active Branch: main" in result

@pytest.mark.asyncio
async def test_get_stats_empty():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store:
        
        # Setup mocks
        mock_store.get_detailed_stats.return_value = {}
        
        with patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=lambda x: str(x))):
            
            # Run tool
            result = await get_stats_impl(root_path="/root")
            
            # Verify output
            assert "Status: Not Indexed" in result
