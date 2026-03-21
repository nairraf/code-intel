import pytest
from unittest.mock import MagicMock, patch

from src.structural_core.models import RefreshRun
from src.tools.status import get_index_status_impl


@pytest.mark.asyncio
async def test_get_index_status_ready_without_edges():
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 5,
        "symbol_count": 42,
        "import_count": 7,
        "edge_count": 0,
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
    mock_ctx.structural_store.get_refresh_run.return_value = RefreshRun(
        project_root="/root",
        last_refresh_at="2026-03-20T12:00:00Z",
        scan_type="incremental",
        status="ok",
        files_scanned=5,
        files_changed=1,
        files_skipped=4,
    )

    with patch("src.tools.structural_common.check_git_dirty", return_value=False):
        result = await get_index_status_impl(root_path="/root", ctx=mock_ctx)

    assert result["status"] == "ok"
    assert result["capabilities"]["structuralNavigation"] is True
    assert result["capabilities"]["impactAnalysis"] is False
    assert result["capabilities"]["semanticSearch"] is False
    assert any("Impact analysis is limited" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_get_index_status_dirty_workspace_is_usable_with_warning():
    mock_ctx = MagicMock()
    refresh_run = RefreshRun(
        project_root="/root",
        last_refresh_at="2026-03-20T12:00:00Z",
        scan_type="full",
        status="ok",
        files_scanned=10,
        files_changed=2,
        files_skipped=8,
    )
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 10,
        "symbol_count": 100,
        "import_count": 15,
        "edge_count": 120,
        "refresh_run": refresh_run,
    }
    mock_ctx.structural_store.get_refresh_run.return_value = refresh_run

    with patch("src.tools.structural_common.check_git_dirty", return_value=True):
        result = await get_index_status_impl(root_path="/root", ctx=mock_ctx)

    assert result["status"] == "ok"
    assert result["freshness"]["structuralState"] == "current"
    assert result["freshness"]["workspaceState"] == "dirty"
    assert result["capabilities"]["structuralNavigation"] is True
    assert result["capabilities"]["impactAnalysis"] is True
    assert any("uncommitted changes" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_get_index_status_missing_index():
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = None
    mock_ctx.structural_store.get_refresh_run.return_value = None

    result = await get_index_status_impl(root_path="/root", ctx=mock_ctx)

    assert result["status"] == "missing"
    assert result["freshness"]["workspaceState"] == "unknown"
    assert result["capabilities"]["structuralNavigation"] is False
    assert result["capabilities"]["impactAnalysis"] is False
    assert any("Run refresh_index" in warning for warning in result["warnings"])