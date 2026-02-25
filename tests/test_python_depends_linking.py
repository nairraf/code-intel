import pytest
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser
from src.knowledge_graph import KnowledgeGraph
from src.storage import VectorStore
from src.linker import SymbolLinker

@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_kg.sqlite"
    kg = KnowledgeGraph(str(db_path))
    vs = VectorStore()
    linker = SymbolLinker(vs, kg)
    parser = CodeParser()
    
    return {
        "kg": kg,
        "vs": vs,
        "linker": linker,
        "parser": parser,
        "root": tmp_path
    }

@pytest.mark.asyncio
async def test_python_depends_explicit_linking(test_env):
    """
    Test that a symbol explicitly imported and used as an argument 
    in Depends() gets linked with 'explicit_import' confidence.
    """
    env = test_env
    project_root = env["root"] / "project"
    project_root.mkdir()
    
    # 1. Dependency Definition
    middleware_dir = project_root / "middleware"
    middleware_dir.mkdir()
    (middleware_dir / "__init__.py").touch()
    
    auth_file = middleware_dir / "firebase_auth.py"
    auth_file.write_text("""
def verify_firebase_token():
    pass
""", encoding="utf-8")

    # 2. Dependency Usage
    api_dir = project_root / "api"
    api_dir.mkdir()
    (api_dir / "__init__.py").touch()
    
    router_file = api_dir / "router.py"
    router_file.write_text("""
from fastapi import Depends
from middleware.firebase_auth import verify_firebase_token

@app.get("/users")
def get_users(db = Depends(verify_firebase_token)):
    pass
""", encoding="utf-8")

    # Parse
    a_chunks = env["parser"].parse_file(str(auth_file), str(project_root))
    r_chunks = env["parser"].parse_file(str(router_file), str(project_root))
    
    all_chunks = a_chunks + r_chunks
    dummy_vectors = [[0.0] * env["vs"].embedding_dims for _ in all_chunks]
    
    # Index
    env["vs"].upsert_chunks(str(project_root), all_chunks, dummy_vectors)
        
    # Link
    for c in all_chunks:
        env["linker"].link_chunk_usages(str(project_root), c)
        
    # Verify definition was found
    def_chunks = env["vs"].find_chunks_by_symbol(str(project_root), "verify_firebase_token")
    assert len(def_chunks) >= 1
    def_chunk_id = def_chunks[0]["id"]
    
    # Check edges
    edges = env["kg"].get_edges(target_id=def_chunk_id, type="call")
    assert len(edges) >= 1, "Expected call edge from user to dependency"
    
    source_id, target_id, t_type, meta = edges[0]
    source_chunk = env["vs"].get_chunk_by_id(str(project_root), source_id)
    assert Path(source_chunk["filename"]).resolve() == router_file.resolve()
    
    # The crucial part: match_type should be explicit_import, not name_match
    assert meta.get("match_type") == "explicit_import"
    assert meta.get("context") == "dependency_injection"
