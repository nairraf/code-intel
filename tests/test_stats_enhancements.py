
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.storage import VectorStore
from src.server import get_stats_impl

@pytest.mark.asyncio
async def test_get_detailed_stats_enhancements():
    # Mock data for storage
    # We need to simulate the Arrow data structure or just mock get_detailed_stats
    vs = VectorStore()
    project_root = "/mock/project"
    
    # Mock return value of get_detailed_stats
    mock_stats = {
        "chunk_count": 100,
        "file_count": 10,
        "languages": {"python": 100},
        "avg_complexity": 5.0,
        "max_complexity": 15,
        "high_risk_symbols": [
            {"symbol": "risky_func", "complexity": 15, "file": "main.py"}
        ],
        # EXPECTED NEW FIELDS:
        "dependency_hubs": [
            {"file": "utils.py", "count": 10},
            {"file": "models.py", "count": 8}
        ],
        "test_gaps": [
            {"symbol": "risky_func", "complexity": 15, "file": "main.py"}
        ],
        "stale_files_count": 3
    }
    
    with patch.object(VectorStore, 'get_detailed_stats', return_value=mock_stats), \
         patch('src.server.batch_get_git_info', return_value={}), \
         patch('src.server.get_active_branch', return_value="feat/god-mode"):
        
        # We need to mock get_active_branch once it's implemented, 
        # but for RED phase we'll just let it fail or mock the server call dependencies.
        
        # For now, let's call the server impl and check if it handles the new fields
        # This will fail because get_stats_impl doesn't use these fields yet.
        result = await get_stats_impl(project_root)
        
        assert "Dependency Hubs" in result
        assert "utils.py (10 imports)" in result
        assert "Test Gaps" in result
        assert "risky_func (15)" in result
        assert "Project Pulse:" in result
        assert "Active Branch: feat/god-mode" in result
        assert "Stale Files:   3" in result

@pytest.mark.asyncio
async def test_get_active_branch():
    from src.git_utils import get_active_branch
    
    with patch('asyncio.create_subprocess_exec') as mock_exec:
        mock_process = MagicMock()
        
        # Proper way to mock asyncio subprocess communicate
        async def mock_communicate():
            return b"main\n", b""
            
        mock_process.communicate = mock_communicate
        mock_process.returncode = 0
        mock_exec.return_value = mock_process
        
        branch = await get_active_branch(".")
        assert branch == "main"
