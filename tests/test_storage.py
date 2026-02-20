import pytest
import shutil
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import VectorStore
from src.models import CodeChunk

@pytest.fixture
def temp_store(tmp_path):
    """Provides a VectorStore with a temporary database."""
    db_uri = tmp_path / "test_lancedb"
    store = VectorStore(uri=str(db_uri))
    yield store
    # Cleanup is handled by tmp_path fixture usually, but just in case
    if db_uri.exists():
        shutil.rmtree(db_uri)

def test_upsert_and_count(temp_store):
    project = "test_project"
    chunks = [
        CodeChunk(id="c1", filename="file1.py", start_line=1, end_line=1, content="code1", type="function", language="python"),
        CodeChunk(id="c2", filename="file1.py", start_line=2, end_line=2, content="code2", type="function", language="python")
    ]
    vectors = [[0.1] * 1024, [0.2] * 1024]
    
    temp_store.upsert_chunks(project, chunks, vectors)
    assert temp_store.count_chunks(project) == 2

def test_upsert_idempotency_by_file(temp_store):
    """Verify that upserting a file replaces its previous chunks."""
    project = "idempotent_project"
    
    # First upsert
    chunks1 = [CodeChunk(id="v1", filename="main.py", start_line=1, end_line=1, content="v1", type="class", language="python")]
    temp_store.upsert_chunks(project, chunks1, [[0.1]*1024])
    assert temp_store.count_chunks(project) == 1
    
    # Second upsert (same file, different IDs)
    chunks2 = [
        CodeChunk(id="v2a", filename="main.py", start_line=1, end_line=5, content="v2a", type="function", language="python"),
        CodeChunk(id="v2b", filename="main.py", start_line=6, end_line=10, content="v2b", type="function", language="python")
    ]
    temp_store.upsert_chunks(project, chunks2, [[0.2]*1024, [0.3]*1024])
    
    assert temp_store.count_chunks(project) == 2
    assert temp_store.get_chunk_by_id(project, "v1") is None
    assert temp_store.get_chunk_by_id(project, "v2a") is not None

def test_get_detailed_stats_real(temp_store):
    project = "stats_project"
    
    # Prepare diverse chunks to hit all branches of get_detailed_stats
    chunks = [
        CodeChunk(
            id="high_comp", filename="engine.py", start_line=1, end_line=100, 
            content="def heavy(): ...", type="function", language="python",
            symbol_name="heavy_logic", complexity=25, 
            dependencies=["os", "sys"], related_tests=[], 
            last_modified="2020-01-01 12:00:00 -0000" # Very stale
        ),
        CodeChunk(
            id="with_tests", filename="utils.py", start_line=1, end_line=20, 
            content="def tool(): ...", type="function", language="python",
            symbol_name="tool_func", complexity=15, 
            dependencies=["pathlib"], related_tests=["test_utils.py"],
            last_modified="2026-01-01 12:00:00 -0000" # Not stale (assuming "now" is 2026)
        ),
        CodeChunk(
            id="simple", filename="ui.js", start_line=1, end_line=5, 
            content="function render() {}", type="function", language="javascript",
            symbol_name="render", complexity=2, 
            dependencies=["react"], last_modified="2026-02-19 12:00:00 -0000"
        )
    ]
    vectors = [[0.1]*1024] * 3
    
    temp_store.upsert_chunks(project, chunks, vectors)
    
    stats = temp_store.get_detailed_stats(project)
    
    assert stats["chunk_count"] == 3
    assert stats["file_count"] == 3
    assert stats["languages"]["python"] == 2
    assert stats["languages"]["javascript"] == 1
    assert stats["max_complexity"] == 25
    assert stats["avg_complexity"] == (25 + 15 + 2) / 3
    
    # Dependency Hubs (most common should be os, sys, pathlib, react - all count 1 here)
    dep_files = [d["file"] for d in stats["dependency_hubs"]]
    assert "os" in dep_files
    
    # Test Gaps: high_comp has complexity 25 and rel_tests []
    gap_symbols = [g["symbol"] for g in stats["test_gaps"]]
    assert "heavy_logic" in gap_symbols
    assert "tool_func" not in gap_symbols # Has tests
    
    # Stale count: heavy_logic is from 2020
    assert stats["stale_files_count"] >= 1

def test_search_real(temp_store):
    project = "search_project"
    chunk = CodeChunk(id="s1", filename="search.py", start_line=1, end_line=1, content="target content", type="function", language="python")
    vec = [0.5] * 1024
    
    temp_store.upsert_chunks(project, [chunk], [vec])
    
    # Search with identical vector
    results = temp_store.search(project, vec, limit=1)
    assert len(results) == 1
    assert results[0]["content"] == "target content"
    assert results[0]["filename"] == "search.py"

def test_clear_project(temp_store):
    project = "wipe_me"
    chunk = CodeChunk(id="w1", filename="ext.py", start_line=1, end_line=1, content="ext", type="function", language="python")
    temp_store.upsert_chunks(project, [chunk], [[0.1]*1024])
    assert temp_store.count_chunks(project) == 1
    
    temp_store.clear_project(project)
    assert temp_store.count_chunks(project) == 0
