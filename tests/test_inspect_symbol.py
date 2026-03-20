import os
import shutil
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server import inspect_symbol, refresh_index
from src.parser import CodeParser
from src.structural_core.refresh import StructuralRefresher
from src.structural_core.store import StructuralStore


@pytest.fixture
def structural_project(tmp_path):
    project_root = tmp_path / "inspect_project"
    project_root.mkdir()
    (project_root / "service.py").write_text(
        "class MyService:\n    def do_work(self):\n        return 'ok'\n",
        encoding="utf-8",
    )
    (project_root / "app.py").write_text(
        "from service import MyService\n\ndef main():\n    service = MyService()\n    return service.do_work()\n",
        encoding="utf-8",
    )
    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_inspect_symbol_returns_exact_definition_and_references(structural_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "inspect.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(structural_project), force_full_scan=True)
        result = await inspect_symbol.fn(
            root_path=str(structural_project),
            symbol_name="MyService",
            include_references=True,
        )

    assert result["status"] == "ok"
    assert result["symbol"] == "MyService"
    assert result["definitions"]
    assert result["definitions"][0]["file"].endswith("service.py")
    assert any(reference["file"].endswith("app.py") for reference in result["references"])
    assert all(reference["confidence"] == "exact" for reference in result["references"])


@pytest.mark.asyncio
async def test_inspect_symbol_reports_missing_exact_match(structural_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "inspect_missing.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(structural_project), force_full_scan=True)
        result = await inspect_symbol.fn(
            root_path=str(structural_project),
            symbol_name="DoesNotExist",
        )

    assert result["status"] == "ok"
    assert result["definitions"] == []
    assert any("No exact structural definition found" in warning for warning in result["warnings"])