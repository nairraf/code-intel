import pytest
import os
import sys
from pathlib import Path

# Fix sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser
from src.knowledge_graph import KnowledgeGraph
from src.storage import VectorStore
from src.linker import SymbolLinker

@pytest.fixture
def test_env(tmp_path):
    # Setup standard components
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
async def test_dart_widget_instantiation_reference(test_env):
    """
    Test that widget instantiation (calling a constructor without 'new')
    is properly recognized as a usage and linked to the widget definition.
    """
    env = test_env
    # Create mock project
    project_root = env["root"] / "project"
    project_root.mkdir()
    
    # 1. Widget Definition
    widget_file = project_root / "login_screen.dart"
    widget_file.write_text("""
class LoginScreen extends StatelessWidget {
  const LoginScreen({Key? key}) : super(key: key);
  
  @override
  Widget build(BuildContext context) {
    return Container();
  }
}
""", encoding="utf-8")

    # 2. Widget Usage
    usage_file = project_root / "auth_gate.dart"
    usage_file.write_text("""
import 'login_screen.dart';

class AuthGate extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    // Missing 'new', should still be recognized as a call to LoginScreen
    return LoginScreen();
  }
}
""", encoding="utf-8")

    # Parse and index both files
    w_chunks = env["parser"].parse_file(str(widget_file), str(project_root))
    u_chunks = env["parser"].parse_file(str(usage_file), str(project_root))
    
    all_chunks = w_chunks + u_chunks
    # VectorStore expects chunks and vectors for upsert
    dummy_vectors = [[0.0] * env["vs"].embedding_dims for _ in all_chunks]
    env["vs"].upsert_chunks(str(project_root), all_chunks, dummy_vectors)
        
    # Link usages
    for c in all_chunks:
        env["linker"].link_chunk_usages(str(project_root), c)
        
    # Verify the definition was found
    def_chunks = env["vs"].find_chunks_by_symbol(str(project_root), "LoginScreen")
    assert len(def_chunks) >= 1
    def_chunk_id = def_chunks[0]["id"]
    
    # Verify the reference edge exists
    edges = env["kg"].get_edges(target_id=def_chunk_id, type="call")
    # Expected: AuthGate -> LoginScreen
    assert len(edges) >= 1
    
    # Verify it came from the usage file
    source_id, target_id, t_type, meta = edges[0]
    source_chunk = env["vs"].get_chunk_by_id(str(project_root), source_id)
    assert Path(source_chunk["filename"]).resolve() == usage_file.resolve()
