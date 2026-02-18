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

def test_clear_graph(temp_graph):
    temp_graph.add_edge("a", "b", "call")
    assert len(temp_graph.get_edges()) == 1
    
    temp_graph.clear()
    assert len(temp_graph.get_edges()) == 0
