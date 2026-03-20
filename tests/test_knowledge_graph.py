import pytest
import sqlite3
import sys
import os
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.knowledge_graph import KnowledgeGraph

@pytest.fixture
def temp_graph(tmp_path):
    db_path = tmp_path / "test_graph.sqlite"
    return KnowledgeGraph(str(db_path))

def test_add_and_get_edge(temp_graph):
    source = "chunk_a"
    target = "chunk_b"
    edge_type = "call"
    meta = {"frequency": 5}
    
    temp_graph.add_edge(source, target, edge_type, meta)
    
    edges = temp_graph.get_edges(source_id=source)
    assert len(edges) == 1
    
    s, t, type_, m = edges[0]
    assert s == source
    assert t == target
    assert type_ == edge_type
    assert m == meta

def test_get_edges_filters(temp_graph):
    # Add multiple edges
    temp_graph.add_edge("a", "b", "call")
    temp_graph.add_edge("a", "c", "import")
    temp_graph.add_edge("d", "b", "inheritance")
    
    # Filter by source
    res_a = temp_graph.get_edges(source_id="a")
    assert len(res_a) == 2
    
    # Filter by target
    res_b = temp_graph.get_edges(target_id="b")
    assert len(res_b) == 2  # a->b, d->b
    
    # Filter by type
    res_import = temp_graph.get_edges(type="import")
    assert len(res_import) == 1
    assert res_import[0][1] == "c"

def test_get_edges_filters_by_project_root(temp_graph):
    temp_graph.add_edge("a", "b", "call", project_root="repo-a")
    temp_graph.add_edge("c", "d", "call", project_root="repo-b")

    repo_a_edges = temp_graph.get_edges(project_root="repo-a")
    repo_b_edges = temp_graph.get_edges(project_root="repo-b")

    assert len(repo_a_edges) == 1
    assert repo_a_edges[0][0] == "a"
    assert len(repo_b_edges) == 1
    assert repo_b_edges[0][0] == "c"

def test_delete_file_edges_and_get_source_files(temp_graph):
    temp_graph.add_edge(
        "source_chunk",
        "target_chunk",
        "call",
        project_root="repo",
        source_filename="src/app.py",
        target_filename="src/service.py",
    )
    temp_graph.add_edge(
        "other_chunk",
        "target_chunk",
        "call",
        project_root="repo",
        source_filename="src/worker.py",
        target_filename="src/service.py",
    )

    source_files = temp_graph.get_source_files("repo", ["src/service.py"])
    assert set(source_files) == {"src/app.py", "src/worker.py"}

    temp_graph.delete_file_edges("repo", ["src/service.py"])
    assert temp_graph.get_edges(project_root="repo") == []

def test_clear_graph(temp_graph):
    temp_graph.add_edge("a", "b", "call")
    assert len(temp_graph.get_edges()) == 1
    
    temp_graph.clear()
    assert len(temp_graph.get_edges()) == 0

def test_persistent_connection_lifecycle(tmp_path):
    db_path = tmp_path / "lifecycle_graph.sqlite"
    kg = KnowledgeGraph(str(db_path))
    
    # Connection is not created until first interaction (after init_db)
    # Actually _init_db is called in __init__, so connection already exists.
    assert kg._conn is not None
    
    # Same connection is reused
    conn1 = kg._conn
    kg.add_edge("a", "b", "call")
    kg.get_edges()
    assert kg._conn is conn1
    
    # Close connection
    kg.close()
    assert kg._conn is None
    
    # Should automatically reopen on next query
    kg.get_edges()
    assert kg._conn is not None
    assert kg._conn is not conn1

def test_close_safe_on_uninitialized():
    # Bypass __init__ completely to test close on pure empty object
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg._conn = None
    kg.close()
    assert kg._conn is None
