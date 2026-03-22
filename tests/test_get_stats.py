import pytest
import sys
import os
from types import SimpleNamespace
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
    mock_ctx.structural_store.list_tracked_files.return_value = []
    mock_ctx.structural_store.list_symbols.return_value = []
    mock_ctx.structural_store.list_imports.return_value = []

    with patch('src.tools.stats.get_active_branch', return_value="main"), \
         patch('src.tools.stats.build_freshness', return_value=({
             "projectRoot": "/root",
             "structuralState": "current",
             "workspaceState": "clean",
             "enrichmentState": "disabled",
             "lastStructuralRefreshAt": "2026-03-20T12:00:00Z",
             "lastEnrichmentAt": None,
             "scope": {"include": None, "exclude": None},
             "warnings": [],
         }, [])):
        result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

        assert result["status"] == "ok"
        assert result["overview"]["indexedSymbols"] == 42
        assert result["projectPulse"]["activeBranch"] == "main"
        assert result["summary"].startswith("5 tracked files")
        assert result["hotspotScope"] == {
            "defaultView": "code",
            "view": "code",
            "filesConsidered": 0,
            "roots": [],
            "include": None,
            "exclude": None,
            "testFilesExcluded": 0,
            "nonCodeFilesExcluded": 0,
        }
        assert result["dependencyHubs"] == {"fanIn": [], "fanOut": []}


@pytest.mark.asyncio
async def test_get_stats_empty():
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = None
    mock_ctx.structural_store.get_refresh_run.return_value = None

    result = await get_stats_impl(root_path="/root", ctx=mock_ctx)

    assert result["status"] == "missing"
    assert "No structural index found for project" in result["summary"]


@pytest.mark.asyncio
async def test_get_stats_splits_code_and_non_code_hotspots():
    project_root = "/root"
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 4,
        "symbol_count": 3,
        "import_count": 1,
        "edge_count": 0,
        "languages": {"python": 3},
        "refresh_run": RefreshRun(
            project_root=project_root,
            last_refresh_at="2026-03-20T12:00:00Z",
            scan_type="full",
            status="ok",
            files_scanned=4,
            files_changed=4,
            files_skipped=0,
        ),
    }
    mock_ctx.structural_store.list_tracked_files.return_value = [
        "/root/src/app.py",
        "/root/tests/test_app.py",
        "/root/docs/PROJECT_PLAN.md",
        "/root/run.json",
    ]
    mock_ctx.structural_store.list_symbols.return_value = [
        SimpleNamespace(
            filename="/root/src/app.py",
            symbol_kind="function_definition",
            end_line=80,
            start_line=1,
            parent_symbol="",
            symbol_name="main",
        )
    ]
    mock_ctx.structural_store.list_imports.return_value = []

    line_counts = {
        "/root/src/app.py": 80,
        "/root/tests/test_app.py": 60,
        "/root/docs/PROJECT_PLAN.md": 300,
        "/root/run.json": 200,
    }

    with patch('src.tools.stats.get_active_branch', return_value="main"), \
         patch('src.tools.stats.build_freshness', return_value=({
             "projectRoot": project_root,
             "structuralState": "current",
             "workspaceState": "clean",
             "enrichmentState": "disabled",
             "lastStructuralRefreshAt": "2026-03-20T12:00:00Z",
             "lastEnrichmentAt": None,
             "scope": {"include": None, "exclude": None},
             "warnings": [],
         }, [])), \
         patch('src.tools.stats._count_file_lines', side_effect=lambda path: line_counts[path]):
        result = await get_stats_impl(root_path=project_root, ctx=mock_ctx)

    assert result["status"] == "ok"
    assert result["hotspotScope"] == {
        "defaultView": "code",
        "view": "code",
        "filesConsidered": 1,
        "roots": [],
        "include": None,
        "exclude": None,
        "testFilesExcluded": 1,
        "nonCodeFilesExcluded": 2,
    }
    assert [entry["file"] for entry in result["topLargeFiles"]] == ["/root/src/app.py"]
    assert [entry["file"] for entry in result["nonCodeLargeFiles"]] == [
        "/root/docs/PROJECT_PLAN.md",
        "/root/run.json",
    ]
    assert result["warnings"] == [
        "Code view excludes test files; use view='tests' for test hotspots or view='all' for the combined view.",
        "Hotspot ranking defaults to code-like files; see nonCodeLargeFiles for excluded tracked files."
    ]


@pytest.mark.asyncio
async def test_get_stats_supports_tests_view_and_scope_filters():
    project_root = "/root"
    mock_ctx = MagicMock()
    mock_ctx.structural_store.get_project_stats.return_value = {
        "tracked_files": 5,
        "symbol_count": 3,
        "import_count": 1,
        "edge_count": 0,
        "languages": {"python": 2, "dart": 1},
        "refresh_run": RefreshRun(
            project_root=project_root,
            last_refresh_at="2026-03-20T12:00:00Z",
            scan_type="full",
            status="ok",
            files_scanned=5,
            files_changed=5,
            files_skipped=0,
        ),
    }
    mock_ctx.structural_store.list_tracked_files.return_value = [
        "/root/src/app.py",
        "/root/tests/test_app.py",
        "/root/test/widget_test.dart",
        "/root/lib/widget.dart",
        "/root/docs/PROJECT_PLAN.md",
    ]
    mock_ctx.structural_store.list_symbols.return_value = [
        SimpleNamespace(
            filename="/root/tests/test_app.py",
            symbol_kind="function_definition",
            end_line=100,
            start_line=1,
            parent_symbol="",
            symbol_name="test_app",
        ),
        SimpleNamespace(
            filename="/root/test/widget_test.dart",
            symbol_kind="function_definition",
            end_line=50,
            start_line=1,
            parent_symbol="",
            symbol_name="main",
        ),
    ]
    mock_ctx.structural_store.list_imports.return_value = []

    line_counts = {
        "/root/src/app.py": 80,
        "/root/tests/test_app.py": 100,
        "/root/test/widget_test.dart": 50,
        "/root/lib/widget.dart": 60,
        "/root/docs/PROJECT_PLAN.md": 300,
    }

    with patch('src.tools.stats.get_active_branch', return_value="main"), \
         patch('src.tools.stats.build_freshness', return_value=({
             "projectRoot": project_root,
             "structuralState": "current",
             "workspaceState": "clean",
             "enrichmentState": "disabled",
             "lastStructuralRefreshAt": "2026-03-20T12:00:00Z",
             "lastEnrichmentAt": None,
             "scope": {"include": "test/**", "exclude": None},
             "warnings": [],
         }, [])), \
         patch('src.tools.stats._count_file_lines', side_effect=lambda path: line_counts[path]):
        result = await get_stats_impl(
            root_path=project_root,
            ctx=mock_ctx,
            view="tests",
            include="test/**",
            roots=["test"],
        )

    assert result["status"] == "ok"
    assert result["hotspotScope"] == {
        "defaultView": "code",
        "view": "tests",
        "filesConsidered": 1,
        "roots": ["test"],
        "include": "test/**",
        "exclude": None,
        "testFilesExcluded": 0,
        "nonCodeFilesExcluded": 0,
    }
    assert [entry["file"] for entry in result["topLargeFiles"]] == ["/root/test/widget_test.dart"]
    assert result["nonCodeLargeFiles"] == []
    assert result["testGapCandidates"] == []
    assert result["refactorCandidates"] == []
