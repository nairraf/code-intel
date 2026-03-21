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


@pytest.fixture(name="impact_project")
def fixture_impact_project(tmp_path):
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


@pytest.fixture(name="dart_impact_project")
def fixture_dart_impact_project(tmp_path):
    project_root = tmp_path / "dart_impact_project"
    lib_dir = project_root / "lib"
    test_dir = project_root / "test"
    lib_dir.mkdir(parents=True)
    test_dir.mkdir()

    (lib_dir / "settings_screen.dart").write_text(
        "class SettingsScreen {}\n",
        encoding="utf-8",
    )
    (lib_dir / "user_menu_button.dart").write_text(
        "import 'settings_screen.dart';\n\nclass UserMenuButton {\n  void openMenu() {\n    final screen = SettingsScreen();\n  }\n}\n",
        encoding="utf-8",
    )
    (test_dir / "settings_screen_test.dart").write_text(
        "import '../lib/settings_screen.dart';\n\nvoid main() {\n  final screen = SettingsScreen();\n}\n",
        encoding="utf-8",
    )
    (lib_dir / "note.dart").write_text(
        "class Note {\n  const Note();\n\n  factory Note.fromFirestore(Object doc) {\n    return const Note();\n  }\n}\n",
        encoding="utf-8",
    )
    (lib_dir / "notes_repository.dart").write_text(
        "import 'note.dart';\n\nclass NotesRepository {\n  Note load(Object doc) {\n    return Note.fromFirestore(doc);\n  }\n\n  List<Note> getNotesStream(Object userId) {\n    return [Note.fromFirestore(userId)];\n  }\n\n  Note getNoteStream(Object userId, Object doc) {\n    return Note.fromFirestore(doc);\n  }\n\n  void updateNote(Note note) {}\n}\n",
        encoding="utf-8",
    )
    (test_dir / "note_test.dart").write_text(
        "import '../lib/note.dart';\n\nvoid main() {\n  final note = Note.fromFirestore(Object());\n}\n",
        encoding="utf-8",
    )
    (lib_dir / "notes_providers.dart").write_text(
        "import 'notes_repository.dart';\n\n"
        "class Ref {\n"
        "  const Ref();\n"
        "  dynamic watch(dynamic value) => value;\n"
        "  dynamic read(dynamic value) => value;\n"
        "}\n\n"
        "const ref = Ref();\n\n"
        "final notesRepositoryProvider = NotesRepository();\n"
        "final notesListProvider = ref.watch(notesRepositoryProvider).getNotesStream('user');\n"
        "final noteProvider = ref.watch(notesRepositoryProvider).getNoteStream('user', Object());\n",
        encoding="utf-8",
    )
    (lib_dir / "notes_screen.dart").write_text(
        "import 'notes_providers.dart';\n\n"
        "class NotesScreen {\n"
        "  void build() {\n"
        "    ref.watch(notesListProvider);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (lib_dir / "home_screen.dart").write_text(
        "import 'notes_providers.dart';\n\n"
        "class HomeScreen {\n"
        "  void build() {\n"
        "    ref.watch(notesListProvider);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (test_dir / "notes_screen_test.dart").write_text(
        "import '../lib/notes_screen.dart';\n\n"
        "void main() {\n"
        "  NotesScreen().build();\n"
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
    (lib_dir / "manual_highlighter_controller.dart").write_text(
        "class ManualHighlighterController {}\n",
        encoding="utf-8",
    )
    (lib_dir / "guided_validation_note_panel.dart").write_text(
        "class GuidedValidationNotePanel {}\n",
        encoding="utf-8",
    )
    (lib_dir / "guided_validation_screen.dart").write_text(
        "import 'manual_highlighter_controller.dart';\n"
        "import 'guided_validation_note_panel.dart';\n\n"
        "class GuidedValidationScreen {\n"
        "  _GuidedValidationScreenState createState() => _GuidedValidationScreenState();\n"
        "}\n\n"
        "class _GuidedValidationScreenState {\n"
        "  late final ManualHighlighterController controller;\n\n"
        "  _GuidedValidationScreenState() {\n"
        "    controller = ManualHighlighterController();\n"
        "  }\n\n"
        "  GuidedValidationNotePanel build() {\n"
        "    return GuidedValidationNotePanel();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (lib_dir / "note_detail_screen.dart").write_text(
        "import 'guided_validation_screen.dart';\n"
        "import 'notes_providers.dart';\n\n"
        "class NoteDetailScreen {\n"
        "  void open() {\n"
        "    final screen = GuidedValidationScreen();\n"
        "    screen.createState().build();\n"
        "  }\n\n"
        "  void save(Object doc) {\n"
        "    ref.read(notesRepositoryProvider).load(doc);\n"
        "    ref.read(notesRepositoryProvider).updateNote(ref.read(noteProvider));\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (test_dir / "guided_validation_screen_test.dart").write_text(
        "import '../lib/guided_validation_screen.dart';\n\n"
        "void main() {\n"
        "  final screen = GuidedValidationScreen();\n"
        "  screen.createState().build();\n"
        "}\n",
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
    assert len(result["candidateTests"]) == 1
    assert any(test["confidence"] == "exact" for test in result["candidateTests"])
    assert any("structural dependency on changed symbol" in test["reasons"] for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_impact_analysis_suppresses_same_file_local_symbol_noise(impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "impact_noise.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    service_file = impact_project / "service.py"
    service_file.write_text(
        "class MyService:\n    def helper(self):\n        return 'ok'\n\n    def do_work(self):\n        return self.helper()\n",
        encoding="utf-8",
    )

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(impact_project),
            changed_files=[str(service_file)],
            include_tests=True,
        )

    service_payload = next(item for item in result["affectedFiles"] if item["file"].endswith("service.py"))

    assert service_payload["reasons"] == ["file changed"]
    assert any(item["file"].endswith("app.py") for item in result["affectedFiles"])
    assert any(item["file"].endswith("test_service.py") for item in result["affectedFiles"])
    assert [item["symbol"] for item in result["affectedSymbols"]] == ["MyService"]


@pytest.mark.asyncio
async def test_impact_analysis_keeps_explicit_nested_symbol_inputs(impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "impact_explicit.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(impact_project),
            changed_symbols=["do_work"],
            include_tests=False,
        )

    assert any(item["symbol"] == "do_work" for item in result["affectedSymbols"])


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

@pytest.mark.asyncio
async def test_impact_analysis_resolves_dart_imported_symbols_and_exact_tests(dart_impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "dart_impact.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store),          patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(dart_impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(dart_impact_project),
            changed_symbols=["SettingsScreen"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("user_menu_button.dart") for item in result["affectedFiles"])
    assert any(test["file"].endswith("settings_screen_test.dart") for test in result["candidateTests"])
    assert any(test["confidence"] == "exact" for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_impact_analysis_resolves_qualified_dart_factory_symbols(dart_impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "dart_factory.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store),          patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(dart_impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(dart_impact_project),
            changed_symbols=["Note.fromFirestore"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("notes_repository.dart") for item in result["affectedFiles"])
    assert any(item["symbol"] == "fromFirestore" for item in result["affectedSymbols"])
    assert any(test["file"].endswith("note_test.dart") for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_impact_analysis_includes_direct_component_collaborators_for_dart_symbols(dart_impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "dart_component.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(dart_impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(dart_impact_project),
            changed_symbols=["GuidedValidationScreen"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("note_detail_screen.dart") for item in result["affectedFiles"])
    assert any(item["file"].endswith("manual_highlighter_controller.dart") for item in result["affectedFiles"])
    assert any(item["file"].endswith("guided_validation_note_panel.dart") for item in result["affectedFiles"])
    assert any(item["symbol"] == "ManualHighlighterController" for item in result["affectedSymbols"])
    assert any(test["file"].endswith("guided_validation_screen_test.dart") for test in result["candidateTests"])


@pytest.mark.asyncio
async def test_impact_analysis_propagates_repository_impacts_through_provider_wrappers(dart_impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "dart_repository_chain.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(dart_impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(dart_impact_project),
            changed_symbols=["NotesRepository"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("note_detail_screen.dart") for item in result["affectedFiles"])
    assert any(item["symbol"] == "notesRepositoryProvider" for item in result["affectedSymbols"])


@pytest.mark.asyncio
async def test_impact_analysis_propagates_named_factory_impacts_through_provider_chain(dart_impact_project, tmp_path):
    structural_store = StructuralStore(str(tmp_path / "dart_factory_chain.sqlite"))
    structural_refresher = StructuralRefresher(structural_store, CodeParser())

    with patch("src.context._context.structural_store", structural_store), \
         patch("src.context._context.structural_refresher", structural_refresher):
        await refresh_index.fn(root_path=str(dart_impact_project), force_full_scan=True)
        result = await impact_analysis.fn(
            root_path=str(dart_impact_project),
            changed_symbols=["Note.fromFirestore"],
            include_tests=True,
        )

    assert result["status"] == "ok"
    assert any(item["file"].endswith("notes_repository.dart") for item in result["affectedFiles"])
    assert any(item["file"].endswith("notes_screen.dart") for item in result["affectedFiles"])
    assert any(item["file"].endswith("home_screen.dart") for item in result["affectedFiles"])
