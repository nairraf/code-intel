import pytest
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, AsyncMock, patch
from src.storage import VectorStore
from src.server import get_stats

@pytest.mark.asyncio
async def test_get_stats_active():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store:
        
        # Setup mocks
        mock_store.count_chunks.return_value = 42
        
        with patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)):
            
            # Run tool
            result = await get_stats.fn(root_path="/root")
            
            # Verify stats in output
            assert "Total Chunks: 42" in result
            assert "Status: Active" in result

@pytest.mark.asyncio
async def test_get_stats_empty():
    # Mock dependencies
    with patch('src.server.vector_store') as mock_store:
        
        # Setup mocks
        mock_store.count_chunks.return_value = 0
        
        with patch('pathlib.Path.resolve', return_value=MagicMock(side_effect=str)):
            
            # Run tool
            result = await get_stats.fn(root_path="/root")
            
            # Verify output
            assert "Status: Not Indexed" in result
