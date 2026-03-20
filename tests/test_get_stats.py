import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import MagicMock, patch
from src.structural_core.models import RefreshRun
from src.tools.stats import get_stats_impl


@pytest.mark.asyncio
async def test_get_stats_active():
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 5,
        "symbol_count": 42,
        "import_count": 7,
        "edge_count": 0,
        "languages": {"python": 42},
        "dependency_hubs": [],
        "refresh_run": RefreshRun(
            project_root="/root",
            last_refresh_at="2026-03-20T12:00:00Z",
            scan_type="incremental",
            status="ok",
            files_scanned=5,
            files_changed=1,
            files_skipped=4,
        ),
    }

    with patch('src.tools.stats.get_active_branch', return_value="main"), \
         patch('src.tools.stats.check_git_dirty', return_value=False):
        result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

        assert "Indexed Symbols:  42" in result
        assert "Stats for:" in result
        assert "Active Branch:" in result
        assert "main" in result
        assert "Project Pulse:" in result


@pytest.mark.asyncio
async def test_get_stats_empty():
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = None

    result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

    assert "No structural index found for project" in result
