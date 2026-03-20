
import pytest
from unittest.mock import MagicMock, patch
from src.structural_core.models import RefreshRun
from src.tools.stats import get_stats_impl


@pytest.mark.asyncio
async def test_get_detailed_stats_enhancements():
    project_root = "/mock/project"

    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 10,
        "symbol_count": 100,
        "import_count": 12,
        "edge_count": 0,
        "languages": {"python": 100},
        "dependency_hubs": [
            {"import_text": "utils", "count": 10},
            {"import_text": "models", "count": 8}
        ],
        "refresh_run": RefreshRun(
            project_root=project_root,
            last_refresh_at="2026-03-05T10:00:00Z",
            scan_type="full",
            status="ok",
            files_scanned=10,
            files_changed=3,
            files_skipped=7,
        ),
    }

    with patch('src.tools.stats.get_active_branch', return_value="feat/new-feature"), \
         patch('src.tools.stats.check_git_dirty', return_value=True):
         
        result = await get_stats_impl(project_root, ctx=mock_ctx)

        assert "Dependency Hubs" in result
        assert "utils (10 imports)" in result
        assert "Project Pulse:" in result
        assert "Active Branch:   feat/new-feature" in result
        assert "Structural State: DIRTY" in result
        assert "Files Changed:   3" in result


@pytest.mark.asyncio
async def test_get_active_branch():
    from src.git_utils import get_active_branch

    with patch('asyncio.create_subprocess_exec') as mock_exec:
        mock_process = MagicMock()

        async def mock_communicate():
            return b"main\n", b""

        mock_process.communicate = mock_communicate
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        branch = await get_active_branch(".")
        assert branch == "main"
