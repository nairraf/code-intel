
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
    mock_ctx.structural_store.list_tracked_files.return_value = []
    mock_ctx.structural_store.list_symbols.return_value = []
    mock_ctx.structural_store.list_imports.return_value = []

    with patch('src.tools.stats.get_active_branch', return_value="feat/new-feature"), \
         patch('src.tools.stats.build_freshness', return_value=({
             "projectRoot": project_root,
             "structuralState": "current",
             "workspaceState": "dirty",
             "enrichmentState": "disabled",
             "lastStructuralRefreshAt": "2026-03-05T10:00:00Z",
             "lastEnrichmentAt": None,
             "scope": {"include": None, "exclude": None},
             "warnings": ["Repository has uncommitted changes since the last structural refresh."],
         }, ["Repository has uncommitted changes since the last structural refresh."])):
         
        result = await get_stats_impl(project_root, ctx=mock_ctx)

        assert result["status"] == "ok"
        assert result["projectPulse"]["activeBranch"] == "feat/new-feature"
        assert result["projectPulse"]["lastScanType"] == "full"
        assert result["warnings"] == ["Repository has uncommitted changes since the last structural refresh."]


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
