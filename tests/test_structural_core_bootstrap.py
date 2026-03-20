from src.parser import CodeParser
from src.structural_core.manifest import plan_refresh
import sqlite3
import json

from src.structural_core.models import FileState, RefreshRun
from src.structural_core.refresh import StructuralRefreshPlanner, StructuralRefresher
from src.structural_core.store import StructuralStore
from src.utils import normalize_path


def test_structural_store_initializes_minimum_tables(tmp_path):
    store = StructuralStore(str(tmp_path / "structural.sqlite"))

    tables = set(store.list_tables())

    assert "edges" in tables
    assert "file_manifest" in tables
    assert "imports" in tables
    assert "refresh_runs" in tables
    assert "symbols" in tables


def test_structural_store_file_manifest_round_trip(tmp_path):
    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    project_root = str(tmp_path / "project")
    first = FileState(filename=str(tmp_path / "project" / "a.py"), size=10, mtime_ns=11, content_hash="abc")
    second = FileState(filename=str(tmp_path / "project" / "b.py"), size=20, mtime_ns=22, content_hash="def")

    store.upsert_file_manifest(project_root, [first, second])
    manifest = store.get_file_manifest(project_root)

    assert manifest[normalize_path(first.filename)] == FileState(
        filename=normalize_path(first.filename),
        size=10,
        mtime_ns=11,
        content_hash="abc",
    )
    assert manifest[normalize_path(second.filename)].content_hash == "def"

    store.delete_file_manifest(project_root, [first.filename])
    manifest_after_delete = store.get_file_manifest(project_root)

    assert normalize_path(first.filename) not in manifest_after_delete
    assert normalize_path(second.filename) in manifest_after_delete


def test_plan_refresh_classifies_added_changed_removed_and_unchanged(tmp_path):
    unchanged = normalize_path(str(tmp_path / "unchanged.py"))
    changed = normalize_path(str(tmp_path / "changed.py"))
    removed = normalize_path(str(tmp_path / "removed.py"))
    added = normalize_path(str(tmp_path / "added.py"))

    stored_manifest = {
        unchanged: FileState(filename=unchanged, size=10, mtime_ns=100, content_hash="aaa"),
        changed: FileState(filename=changed, size=10, mtime_ns=100, content_hash="bbb"),
        removed: FileState(filename=removed, size=10, mtime_ns=100, content_hash="ccc"),
    }
    observed_manifest = {
        unchanged: FileState(filename=unchanged, size=10, mtime_ns=100, content_hash="aaa"),
        changed: FileState(filename=changed, size=11, mtime_ns=101, content_hash="ddd"),
        added: FileState(filename=added, size=12, mtime_ns=102, content_hash="eee"),
    }

    diff = plan_refresh(stored_manifest, observed_manifest)

    assert diff.added == (added,)
    assert diff.changed == (changed,)
    assert diff.removed == (removed,)
    assert diff.unchanged == (unchanged,)


def test_structural_refresh_planner_reads_store_manifest(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = project_root / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")

    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    planner = StructuralRefreshPlanner(store)

    initial_diff = planner.plan(str(project_root), [str(source_file)])
    assert initial_diff.added == (normalize_path(str(source_file)),)

    observed = planner.collect_observed_manifest([str(source_file)])
    store.upsert_file_manifest(str(project_root), list(observed.values()))

    second_diff = planner.plan(str(project_root), [str(source_file)])
    assert second_diff.unchanged == (normalize_path(str(source_file)),)


def test_structural_store_persists_refresh_runs(tmp_path):
    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    project_root = normalize_path(str(tmp_path / "project"))

    store.upsert_refresh_run(
        RefreshRun(
            project_root=project_root,
            last_refresh_at="2026-03-20T12:00:00Z",
            scan_type="incremental",
            status="ok",
            files_scanned=4,
            files_changed=1,
            files_skipped=3,
        )
    )

    refresh_run = store.get_refresh_run(project_root)

    assert refresh_run is not None
    assert refresh_run.files_changed == 1
    assert refresh_run.scan_type == "incremental"


def test_structural_refresher_persists_exact_symbols_and_imports(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "service.py").write_text(
        "class MyService:\n    def do_work(self):\n        return 'ok'\n",
        encoding="utf-8",
    )
    app_file = project_root / "app.py"
    app_file.write_text(
        "from service import MyService\n\ndef main():\n    service = MyService()\n    return service.do_work()\n",
        encoding="utf-8",
    )

    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    refresher = StructuralRefresher(store, CodeParser())

    result = refresher.refresh(
        str(project_root),
        [str(project_root / "service.py"), str(app_file)],
        force_full_scan=True,
    )

    symbols = store.list_symbols(str(project_root))
    imports = store.list_imports(str(project_root), str(app_file))

    assert result.scan_type == "full"
    assert result.files_changed == 2
    assert any(symbol.symbol_name == "MyService" for symbol in symbols)
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(record.import_text == "service" for record in imports)
    assert any(record.import_text == "service::MyService" for record in imports)

    edges = store.list_edges(str(project_root), source_filename=str(app_file))
    assert any(edge.target_filename == normalize_path(str(project_root / "service.py")) for edge in edges)
    assert any(json.loads(edge.metadata_json)["match_type"] == "explicit_import" for edge in edges)


def test_structural_refresher_removes_deleted_file_state(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    service_file = project_root / "service.py"
    service_file.write_text(
        "class MyService:\n    pass\n",
        encoding="utf-8",
    )

    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    refresher = StructuralRefresher(store, CodeParser())

    refresher.refresh(str(project_root), [str(service_file)], force_full_scan=True)
    assert store.list_symbols(str(project_root), str(service_file))

    service_file.unlink()
    result = refresher.refresh(str(project_root), [], force_full_scan=False)

    assert result.files_removed == 1
    assert store.list_symbols(str(project_root), str(service_file)) == []
    assert store.get_file_manifest(str(project_root)) == {}


def test_structural_store_reports_project_stats(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = project_root / "service.py"
    source_file.write_text("class MyService:\n    pass\n", encoding="utf-8")

    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    refresher = StructuralRefresher(store, CodeParser())
    refresher.refresh(str(project_root), [str(source_file)], force_full_scan=True)

    stats = store.get_project_stats(str(project_root))

    assert stats is not None
    assert stats["tracked_files"] == 1
    assert stats["symbol_count"] >= 1
    assert stats["refresh_run"] is not None


def test_structural_store_migrates_legacy_edges_primary_key(tmp_path):
    db_path = tmp_path / "structural.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE edges (
            project_root TEXT NOT NULL,
            source_symbol_id TEXT NOT NULL,
            target_symbol_id TEXT NOT NULL,
            edge_kind TEXT NOT NULL,
            source_filename TEXT NOT NULL,
            target_filename TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind)
        );

        INSERT INTO edges (
            project_root, source_symbol_id, target_symbol_id, edge_kind,
            source_filename, target_filename, metadata_json
        ) VALUES (
            'd:/repo', 'source-1', 'target-1', 'call',
            'd:/repo/app.py', 'd:/repo/service.py', '{"line": 3}'
        );
        """
    )
    conn.commit()
    conn.close()

    store = StructuralStore(str(db_path))
    edges = store.list_edges("d:/repo")
    schema_sql = store._get_conn().execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'edges'"
    ).fetchone()[0]

    assert len(edges) == 1
    assert edges[0].source_symbol_id == "source-1"
    assert "metadata_json" in schema_sql
    assert "PRIMARY KEY (project_root, source_symbol_id, target_symbol_id, edge_kind, metadata_json)" in schema_sql


def test_structural_refresher_relinks_unchanged_callers_after_target_chunk_id_drift(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    service_file = project_root / "service.py"
    app_file = project_root / "app.py"

    service_file.write_text(
        "class MyService:\n    def do_work(self):\n        return 'v1'\n",
        encoding="utf-8",
    )
    app_file.write_text(
        "from service import MyService\n\ndef main():\n    service = MyService()\n    return service.do_work()\n",
        encoding="utf-8",
    )

    store = StructuralStore(str(tmp_path / "structural.sqlite"))
    refresher = StructuralRefresher(store, CodeParser())
    refresher.refresh(str(project_root), [str(service_file), str(app_file)], force_full_scan=True)

    initial_edges = store.list_edges(str(project_root), source_filename=str(app_file))
    assert initial_edges
    old_target_ids = {edge.target_symbol_id for edge in initial_edges}

    service_file.write_text(
        "class MyService:\n    def do_work(self):\n        message = 'v2'\n        return message\n",
        encoding="utf-8",
    )

    result = refresher.refresh(
        str(project_root),
        [str(service_file)],
        force_full_scan=False,
        prune_missing_files=False,
    )

    relinked_edges = store.list_edges(str(project_root), source_filename=str(app_file))
    assert relinked_edges
    assert result.files_scanned == 1
    assert set(old_target_ids) != {edge.target_symbol_id for edge in relinked_edges}