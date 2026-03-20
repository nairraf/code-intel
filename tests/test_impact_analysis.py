import os
import shutil
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server import impact_analysis, refresh_index
from src.parser import CodeParser
from src.structural_core.refresh import StructuralRefresher
from src.structural_core.store import StructuralStore


@pytest.fixture
def impact_project(tmp_path):
    project_root = tmp_path / "impact_project"
    tests_dir = project_root / "tests"
    project_root.mkdir()
    tests_dir.mkdir()
    (project_root / "service.py").write_text(
        "class MyService:\n    def do_work(self):\n        return 'ok'\n",
        encoding="utf-8",
    )
    (project_root / "app.py").write_text(
        "from service import MyService\n\ndef main():\n    service = MyService()\n    return service.do_work()\n",
        encoding="utf-8",
    )
    (tests_dir / "test_service.py").write_text(
        "from service import MyService\n\ndef test_service():\n    assert MyService().do_work() == 'ok'\n",
        encoding="utf-8",
    )
    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_impact_analysis_finds_affected_files_symbols_and_tests(impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "impact.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    service_file = str(impact_project / "service.py")

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(impact_project),
            changed_files=[service_file],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("service.py") for item in result["affectedFiles"])
    assert any(item["file"].endswith("app.py") for item in result["affectedFiles"])
    assert any(item["symbol"] == "MyService" for item in result["affectedSymbols"])
    assert any(test["file"].endswith("test_service.py") for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_impact_analysis_accepts_patch_text_inputs(impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "impact_patch.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    patch_text = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@
-class MyService:
+class MyService:
"""

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(impact_project),
            patch_text=patch_text,
            include_tests=False,
        )

    assert result["status"] == "ok"
    assert any(item["symbol"] == "MyService" for item in result["affectedSymbols"])
    assert any("Patch text was parsed heuristically" in warning for warning in result["warnings"])