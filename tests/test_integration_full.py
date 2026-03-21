import pytest
import os
import sys
import shutil
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser
from src.server import get_index_status, refresh_index, search_code, get_stats
from src.structural_core.refresh import StructuralRefresher
from src.structural_core.store import StructuralStore


@pytest.fixture(name="dummy_project")
def fixture_dummy_project(tmp_path):
    """Creates a small project with a few files."""
    project_root = tmp_path / "integration_proj"
    project_root.mkdir()

    (project_root / "main.py").write_text("""
def hello():
    \"\"\"This is a test function.\"\"\"
    print("Hello World")

class Greeter:
    def __init__(self):
        pass
    def greet(self):
        hello()
""")

    (project_root / "utils.py").write_text("""
def add(a, b):
    return a + b
""")

    (project_root / "styles.css").write_text(".body { color: red; }")

    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_end_to_end_flow(dummy_project, tmp_path):
    structural_db_path = tmp_path / "integration_structural.sqlite"

    structural_store = StructuralStore(str(structural_db_path))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):

        # 1. Run Refresh Index
        refresh_result = await refresh_index.fn(root_path=str(dummy_project))
        assert "Indexing Complete" in refresh_result
        assert "Files Scanned: 3" in refresh_result
        assert "Tracked Files: 3" in refresh_result
        assert "Elapsed Time:" in refresh_result

        # 2. Disabled legacy wrappers fail clearly
        search_result = await search_code.fn(query="hello", root_path=str(dummy_project))
        assert "disabled on feature/structural-context-pivot" in search_result

        # 3. Get Stats
        stats_result = await get_stats.fn(root_path=str(dummy_project))
        assert "Tracked Files:    3" in stats_result
        assert "Indexed Symbols:" in stats_result
        assert "Project Pulse:" in stats_result

        status_result = await get_index_status.fn(root_path=str(dummy_project))
        assert status_result["status"] == "ok"
        assert status_result["capabilities"]["structuralNavigation"] is True
        assert status_result["capabilities"]["impactAnalysis"] is True

        # 4. Incremental update check
        (dummy_project / "new.py").write_text("def extra(): pass")
        refresh_result_inc = await refresh_index.fn(root_path=str(dummy_project))
        assert "Incremental Structural Update" in refresh_result_inc
        assert "Files Scanned: 4 (3 skipped)" in refresh_result_inc
        assert "Tracked Files: 4" in refresh_result_inc
        assert "Elapsed Time:" in refresh_result_inc


@pytest.mark.asyncio
async def test_no_change_incremental_skips_rehashing(dummy_project, tmp_path):
    structural_db_path = tmp_path / "manifest_structural.sqlite"

    structural_store = StructuralStore(str(structural_db_path))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):

        await refresh_index.fn(root_path=str(dummy_project), force_full_scan=True)

        with patch("src.indexer._hash_file", side_effect=AssertionError("unchanged files should not be rehashed")):
            refresh_result = await refresh_index.fn(root_path=str(dummy_project), force_full_scan=False)

        assert "All 3 files unchanged" in refresh_result
        assert "Tracked Files: 3" in refresh_result
        assert "Elapsed Time:" in refresh_result


@pytest.mark.asyncio
async def test_incremental_hashes_only_changed_files(dummy_project, tmp_path):
    structural_db_path = tmp_path / "manifest_changed_structural.sqlite"

    structural_store = StructuralStore(str(structural_db_path))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):

        await refresh_index.fn(root_path=str(dummy_project), force_full_scan=True)

        (dummy_project / "utils.py").write_text("""
def add(a, b):
    result = a + b
    return result
""")

        with patch("src.indexer._hash_file", side_effect=AssertionError("structural refresh should not hash files")) as mock_hash:
            refresh_result = await refresh_index.fn(root_path=str(dummy_project), force_full_scan=False)

        mock_hash.assert_not_called()
        assert "Files Scanned: 3 (2 skipped)" in refresh_result
        assert "Files Changed: 1" in refresh_result
        assert "Elapsed Time:" in refresh_result


@pytest.mark.asyncio
async def test_refresh_index_persists_structural_core_state(dummy_project, tmp_path):
    structural_db_path = tmp_path / "structural_state.sqlite"

    structural_store = StructuralStore(str(structural_db_path))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):

        await refresh_index.fn(root_path=str(dummy_project), force_full_scan=True)

        symbols = structural_store.list_symbols(str(dummy_project))
        imports = structural_store.list_imports(str(dummy_project), str(dummy_project / "main.py"))
        refresh_run = structural_store.get_refresh_run(str(dummy_project))

        assert any(symbol.symbol_name == "hello" for symbol in symbols)
        assert any(symbol.symbol_name == "Greeter" for symbol in symbols)
        assert imports == []
        assert refresh_run is not None
        assert refresh_run.scan_type == "full"
