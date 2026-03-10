import pytest
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser
from src.knowledge_graph import KnowledgeGraph
from src.storage import VectorStore
from src.linker import SymbolLinker
from src.tools.references import find_references_impl

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
    
    matching_edges = [edge for edge in edges if edge[3].get("context") == "dependency_injection"]
    assert matching_edges, "Expected an explicit dependency_injection edge"

    source_id, _, _, meta = matching_edges[0]
    source_chunk = env["vs"].get_chunk_by_id(str(project_root), source_id)
    assert Path(source_chunk["filename"]).resolve() == router_file.resolve()

    # The crucial part: match_type should be explicit_import, not name_match
    assert meta.get("match_type") == "explicit_import"
    assert meta.get("context") == "dependency_injection"


@pytest.mark.asyncio
async def test_find_references_reports_dependency_injection_metadata(test_env):
    env = test_env
    project_root = env["root"] / "project"
    project_root.mkdir()

    middleware_dir = project_root / "middleware"
    middleware_dir.mkdir()
    (middleware_dir / "__init__.py").touch()
    auth_file = middleware_dir / "firebase_auth.py"
    auth_file.write_text(
        """
def verify_firebase_token():
    pass
""",
        encoding="utf-8",
    )

    api_dir = project_root / "api"
    api_dir.mkdir()
    (api_dir / "__init__.py").touch()
    router_file = api_dir / "router.py"
    router_file.write_text(
        """
from fastapi import Depends
from middleware.firebase_auth import verify_firebase_token

def get_users(user = Depends(verify_firebase_token)):
    pass
""",
        encoding="utf-8",
    )

    chunks = env["parser"].parse_file(str(auth_file), str(project_root)) + env["parser"].parse_file(
        str(router_file), str(project_root)
    )
    vectors = [[0.0] * env["vs"].embedding_dims for _ in chunks]
    env["vs"].upsert_chunks(str(project_root), chunks, vectors)

    for chunk in chunks:
        env["linker"].link_chunk_usages(str(project_root), chunk)

    class DummyCtx:
        vector_store = env["vs"]
        knowledge_graph = env["kg"]

    result = await find_references_impl("verify_firebase_token", str(project_root), DummyCtx())

    assert "High Confidence: explicit_import" in result
    assert "Reference Kind: dependency_injection" in result


@pytest.mark.asyncio
async def test_find_references_reports_python_import_and_override_metadata(test_env):
    env = test_env
    project_root = env["root"] / "project_imports"
    project_root.mkdir()

    middleware_dir = project_root / "middleware"
    middleware_dir.mkdir()
    (middleware_dir / "__init__.py").touch()
    auth_file = middleware_dir / "firebase_auth.py"
    auth_file.write_text(
        """
def verify_firebase_token():
    pass

def override_verify_firebase_token():
    pass
""",
        encoding="utf-8",
    )

    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_main.py"
    test_file.write_text(
        """
from middleware.firebase_auth import verify_firebase_token, override_verify_firebase_token

app.dependency_overrides[verify_firebase_token] = override_verify_firebase_token
""",
        encoding="utf-8",
    )

    chunks = env["parser"].parse_file(str(auth_file), str(project_root)) + env["parser"].parse_file(
        str(test_file), str(project_root)
    )
    vectors = [[0.0] * env["vs"].embedding_dims for _ in chunks]
    env["vs"].upsert_chunks(str(project_root), chunks, vectors)

    for chunk in chunks:
        env["linker"].link_chunk_usages(str(project_root), chunk)

    class DummyCtx:
        vector_store = env["vs"]
        knowledge_graph = env["kg"]

    result = await find_references_impl("verify_firebase_token", str(project_root), DummyCtx())

    assert "test_main.py" in result
    assert "Reference Kind: import" in result
    assert "Reference Kind: override_registration" in result
    assert "High Confidence: explicit_import" in result
