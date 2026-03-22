import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser
from src.server import get_stats, impact_analysis, refresh_index
from src.structural_core.refresh import StructuralRefresher
from src.structural_core.store import StructuralStore


def _structural_runtime(tmp_path, name: str) -> tuple[StructuralStore, StructuralRefresher]:
    structural_store = StructuralStore(str(tmp_path / f"{name}.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())
    return structural_store, structural_refresher


@pytest.fixture(name="selos_dart_project")
def fixture_selos_dart_project(tmp_path):
    project_root = tmp_path / "selos_dart_project"
    lib_dir = project_root / "lib"
    test_dir = project_root / "test"
    py_tests_dir = project_root / "tests"
    lib_dir.mkdir(parents=True)
    test_dir.mkdir()
    py_tests_dir.mkdir()

    (lib_dir / "theme_providers.dart").write_text(
        "class Ref {\n"
        "  const Ref();\n"
        "  dynamic watch(dynamic value) => value;\n"
        "  dynamic read(dynamic value) => value;\n"
        "}\n\n"
        "const ref = Ref();\n"
        "const activeVisualThemeIdProvider = 'midnight';\n",
        encoding="utf-8",
    )

    gradient_sections = "".join(
        f"  String section{index}() => 'gradient-{index}';\n"
        for index in range(1, 81)
    )
    (lib_dir / "gradient_scaffold.dart").write_text(
        "import 'theme_providers.dart';\n\n"
        "class GradientScaffold {\n"
        "  const GradientScaffold();\n"
        f"{gradient_sections}"
        "  String themeId() => activeVisualThemeIdProvider;\n"
        "}\n",
        encoding="utf-8",
    )

    for filename, class_name in [
        ("settings_screen.dart", "SettingsScreen"),
        ("auth_gate.dart", "AuthGate"),
        ("guided_validation_screen.dart", "GuidedValidationScreen"),
        ("prayer_requests_screen.dart", "PrayerRequestsScreen"),
        ("app_shell.dart", "AppShell"),
        ("profile_menu_button.dart", "ProfileMenuButton"),
    ]:
        (lib_dir / filename).write_text(
            "import 'gradient_scaffold.dart';\n\n"
            f"class {class_name} {{\n"
            "  GradientScaffold build() {\n"
            "    return const GradientScaffold();\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )

    (lib_dir / "note.dart").write_text(
        "class Note {\n"
        "  const Note();\n\n"
        "  factory Note.fromFirestore(Object doc) {\n"
        "    return const Note();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "notes_repository.dart").write_text(
        "import 'note.dart';\n\n"
        "class NotesRepository {\n"
        "  Note load(Object doc) {\n"
        "    return Note.fromFirestore(doc);\n"
        "  }\n\n"
        "  List<Note> getNotesStream(Object userId) {\n"
        "    return [Note.fromFirestore(userId)];\n"
        "  }\n\n"
        "  Note getNoteStream(Object userId, Object doc) {\n"
        "    return Note.fromFirestore(doc);\n"
        "  }\n\n"
        "  void updateNote(Note note) {}\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "notes_providers.dart").write_text(
        "import 'theme_providers.dart';\n"
        "import 'note.dart';\n"
        "import 'notes_repository.dart';\n\n"
        "final notesRepositoryProvider = NotesRepository();\n"
        "final notesListProvider = ref.watch(notesRepositoryProvider).getNotesStream('user');\n"
        "final noteProvider = ref.watch(notesRepositoryProvider).getNoteStream('user', Object());\n",
        encoding="utf-8",
    )

    (lib_dir / "note_save_service.dart").write_text(
        "import 'note.dart';\n"
        "import 'notes_providers.dart';\n\n"
        "class NoteSaveService {\n"
        "  void save(Note note) {\n"
        "    ref.read(notesRepositoryProvider).updateNote(note);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "home_screen.dart").write_text(
        "import 'gradient_scaffold.dart';\n"
        "import 'notes_providers.dart';\n\n"
        "class HomeScreen {\n"
        "  void build() {\n"
        "    const GradientScaffold();\n"
        "    ref.watch(notesListProvider);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "notes_screen.dart").write_text(
        "import 'gradient_scaffold.dart';\n"
        "import 'notes_providers.dart';\n\n"
        "class NotesScreen {\n"
        "  void build() {\n"
        "    const GradientScaffold();\n"
        "    ref.watch(notesListProvider);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "note_detail_screen.dart").write_text(
        "import 'gradient_scaffold.dart';\n"
        "import 'notes_providers.dart';\n\n"
        "class NoteDetailScreen {\n"
        "  void open(Object doc) {\n"
        "    const GradientScaffold();\n"
        "    ref.read(notesRepositoryProvider).load(doc);\n"
        "    ref.read(notesRepositoryProvider).updateNote(ref.read(noteProvider));\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "note_editor_screen.dart").write_text(
        "import 'note.dart';\n"
        "import 'note_save_service.dart';\n\n"
        "class NoteEditorScreen {\n"
        "  void submit() {\n"
        "    NoteSaveService().save(const Note());\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (lib_dir / "main.dart").write_text(
        "import 'gradient_scaffold.dart';\n"
        "import 'theme_providers.dart';\n\n"
        "class SelosApp {\n"
        "  void build() {\n"
        "    ref.watch(activeVisualThemeIdProvider);\n"
        "    const GradientScaffold();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    (test_dir / "main_test.dart").write_text(
        "import '../lib/main.dart';\n\n"
        "void main() {\n"
        "  SelosApp().build();\n"
        "}\n",
        encoding="utf-8",
    )

    (test_dir / "theme_provider_test.dart").write_text(
        "import '../lib/theme_providers.dart';\n\n"
        "void main() {\n"
        "  ref.watch(activeVisualThemeIdProvider);\n"
        "}\n",
        encoding="utf-8",
    )

    (test_dir / "home_screen_test.dart").write_text(
        "import '../lib/home_screen.dart';\n\n"
        "void main() {\n"
        "  HomeScreen().build();\n"
        "}\n",
        encoding="utf-8",
    )

    (py_tests_dir / "test_theme_provider.py").write_text(
        "def test_theme_provider_smoke():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)


@pytest.fixture(name="selos_python_project")
def fixture_selos_python_project(tmp_path):
    project_root = tmp_path / "selos_python_project"
    app_dir = project_root / "app"
    middleware_dir = app_dir / "middleware"
    routers_dir = app_dir / "routers"
    tests_dir = project_root / "tests"
    middleware_dir.mkdir(parents=True)
    routers_dir.mkdir()
    tests_dir.mkdir()

    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (middleware_dir / "__init__.py").write_text("", encoding="utf-8")
    (routers_dir / "__init__.py").write_text("", encoding="utf-8")

    (middleware_dir / "firebase_auth.py").write_text(
        "def verify_firebase_token():\n"
        "    return {'uid': 'selos-user'}\n",
        encoding="utf-8",
    )

    (routers_dir / "analysis.py").write_text(
        "from fastapi import Depends\n"
        "from app.middleware.firebase_auth import verify_firebase_token\n\n"
        "def analyze(payload: dict, user=Depends(verify_firebase_token)):\n"
        "    return {'ok': True, 'user': user}\n",
        encoding="utf-8",
    )

    (tests_dir / "test_main.py").write_text(
        "from app.middleware.firebase_auth import verify_firebase_token\n"
        "from app.routers.analysis import analyze\n\n"
        "def test_analyze_smoke():\n"
        "    user = verify_firebase_token()\n"
        "    assert analyze({}, user)['ok'] is True\n",
        encoding="utf-8",
    )

    (tests_dir / "test_smoke.py").write_text(
        "def test_smoke():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    yield project_root
    if project_root.exists():
        shutil.rmtree(project_root)


@pytest.mark.asyncio
async def test_selos_gradient_scaffold_stays_hotspot_and_dependency_hub(selos_dart_project, tmp_path):
    structural_store, structural_refresher = _structural_runtime(tmp_path, "selos_gradient")

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(selos_dart_project), force_full_scan=True)
        result = await get_stats.fn(root_path=str(selos_dart_project), view="code", roots=["lib"])

    assert result["status"] == "ok"
    assert any(entry["file"].endswith("gradient_scaffold.dart") for entry in result["topLargeFiles"])
    gradient_hub = next(
        (
            entry for entry in result["dependencyHubs"]["fanIn"]
            if entry["scope"] == "internal" and entry["target"].endswith("gradient_scaffold.dart")
        ),
        None,
    )
    assert gradient_hub is not None
    assert gradient_hub["imports"] >= 7


@pytest.mark.asyncio
async def test_selos_notes_repository_reaches_named_dart_consumers(selos_dart_project, tmp_path):
    structural_store, structural_refresher = _structural_runtime(tmp_path, "selos_notes")

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(selos_dart_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(selos_dart_project),
            changed_symbols=["NotesRepository"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    affected_files = {Path(item["file"]).name for item in result["affectedFiles"]}
    assert {
        "notes_providers.dart",
        "note_save_service.dart",
        "home_screen.dart",
        "note_detail_screen.dart",
        "note_editor_screen.dart",
        "notes_screen.dart",
    }.issubset(affected_files)
    assert any(item["symbol"] == "notesRepositoryProvider" for item in result["affectedSymbols"])


@pytest.mark.asyncio
async def test_selos_active_visual_theme_provider_keeps_dart_side_test_scope(selos_dart_project, tmp_path):
    structural_store, structural_refresher = _structural_runtime(tmp_path, "selos_theme")

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(selos_dart_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(selos_dart_project),
            changed_symbols=["activeVisualThemeIdProvider"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("main.dart") for item in result["affectedFiles"])
    assert result["candidateTests"]
    assert any(test["file"].endswith("main_test.dart") for test in result["candidateTests"])
    assert all(test["file"].endswith(".dart") for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_selos_verify_firebase_token_prefers_explicit_python_test(selos_python_project, tmp_path):
    structural_store, structural_refresher = _structural_runtime(tmp_path, "selos_python")

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(selos_python_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(selos_python_project),
            changed_symbols=["verify_firebase_token"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("analysis.py") for item in result["affectedFiles"])
    assert result["candidateTests"]
    assert result["candidateTests"][0]["file"].endswith("test_main.py")
    assert result["candidateTests"][0]["confidence"] in {"exact", "high"}
    assert any(
        "explicit import" in reason or "structural dependency on changed symbol" in reason
        for reason in result["candidateTests"][0]["reasons"]
    )
    assert all(test["file"].endswith(".py") for test in result["candidateTests"])