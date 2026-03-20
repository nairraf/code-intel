import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import patch
from src.server import refresh_index as refresh_index_tool
from src.structural_core.models import StructuralRefreshResult


@pytest.mark.asyncio
async def test_force_full_scan():
    with patch('src.context._context.structural_refresher') as mock_structural_refresher, \
         patch('src.context._context.structural_store') as mock_structural_store, \
         patch('src.indexer.os.walk') as mock_walk:

        mock_structural_refresher.refresh.return_value = StructuralRefreshResult(
            project_root="/root",
            scan_type="full",
            files_scanned=1,
            files_changed=1,
            files_skipped=0,
            files_removed=0,
            changed_files=("/root/test.py",),
        )
        mock_structural_store.get_project_stats.return_value = {
            "tracked_files": 1,
            "symbol_count": 3,
            "import_count": 1,
            "edge_count": 0,
        }

        mock_walk.return_value = [("/root", [], ["test.py"])]

        with patch('pathlib.Path.exists', return_value=True):

            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=True)

            assert "Full Structural Refresh" in result
            assert "Tracked Files: 1" in result
            assert "Indexed Symbols: 3" in result
            assert "Elapsed Time:" in result


@pytest.mark.asyncio
async def test_incremental_scan():
    with patch('src.context._context.structural_refresher') as mock_structural_refresher, \
         patch('src.context._context.structural_store') as mock_structural_store, \
         patch('src.indexer.os.walk') as mock_walk:

        mock_structural_refresher.refresh.return_value = StructuralRefreshResult(
            project_root="/root",
            scan_type="incremental",
            files_scanned=1,
            files_changed=1,
            files_skipped=0,
            files_removed=0,
            changed_files=("/root/test.py",),
        )
        mock_structural_store.get_project_stats.return_value = {
            "tracked_files": 1,
            "symbol_count": 3,
            "import_count": 1,
            "edge_count": 0,
        }

        mock_walk.return_value = [("/root", [], ["test.py"])]

        with patch('pathlib.Path.exists', return_value=True):

            result = await refresh_index_tool.fn(root_path="/root", force_full_scan=False)

            assert "Incremental Structural Update" in result
            assert "Tracked Files: 1" in result
            assert "Indexed Symbols: 3" in result
            assert "Elapsed Time:" in result
