import pytest
import shutil
from pathlib import Path
from src.server import find_definition, find_references, mcp, refresh_index, search_code
from src.structural_core.models import StructuralRefreshResult


@pytest.mark.asyncio
async def test_refresh_index_flow(mocker):
    project_root = Path("temp_proj_sys")
    project_root.mkdir(exist_ok=True)
    (project_root / "file1.py").write_text("def test(): pass")

    try:
        mock_structural_refresher = mocker.patch("src.context._context.structural_refresher")
        mock_structural_store = mocker.patch("src.context._context.structural_store")
        mock_structural_refresher.refresh.return_value = StructuralRefreshResult(
            project_root=str(project_root),
            scan_type="incremental",
            files_scanned=1,
            files_changed=1,
            files_skipped=0,
            files_removed=0,
            changed_files=(str(project_root / "file1.py"),),
        )
        mock_structural_store.get_project_stats.return_value = {
            "tracked_files": 1,
            "symbol_count": 1,
            "import_count": 0,
            "edge_count": 0,
        }

        result = await refresh_index.fn(str(project_root))

        assert "Indexing Complete" in result
        assert "Files Scanned: 1" in result
        assert "Tracked Files: 1" in result
    finally:
        if project_root.exists():
            shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_search_code_flow():
    result = await search_code.fn("my query", root_path="fake_project")
    assert "search_code is disabled" in result


@pytest.mark.asyncio
async def test_disabled_legacy_tools_are_hidden_from_mcp_surface():
    tool_map = await mcp.get_tools()

    assert "refresh_index" in tool_map
    assert "get_stats" in tool_map
    assert "get_index_status" in tool_map
    assert "inspect_symbol" in tool_map
    assert "impact_analysis" in tool_map
    assert "search_code" not in tool_map
    assert "find_definition" not in tool_map
    assert "find_references" not in tool_map

    assert "find_definition is disabled" in await find_definition.fn("file.py", 1, "symbol", "root")
    assert "find_references is disabled" in await find_references.fn("symbol", "root")


@pytest.mark.asyncio
async def test_refresh_index_missing_path():
    result = await refresh_index.fn("non_existent_path_xyz")
    assert "Error: Path" in result
    assert "does not exist" in result
