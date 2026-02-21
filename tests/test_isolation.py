import pytest
import asyncio
from pathlib import Path
from src.parser import CodeParser
from src.storage import VectorStore
from src.embeddings import OllamaClient
from src.models import CodeChunk
from src.config import EMBEDDING_DIMENSIONS


@pytest.mark.asyncio
async def test_strict_isolation():
    store = VectorStore(uri="./test_vault_iso")
    
    project_a = str(Path("./proj_a").resolve())
    project_b = str(Path("./proj_b").resolve())
    
    # Ensure they exist (as strings/paths)
    Path(project_a).mkdir(exist_ok=True)
    Path(project_b).mkdir(exist_ok=True)
    
    try:
        # 1. Add data to Project A
        chunk_a = CodeChunk(
            id="a1", filename="file_a.py", start_line=1, end_line=1,
            content="def secret_a(): pass", type="function", language="python",
            symbol_name="secret_a", parent_symbol=None, signature=None, docstring=None, decorators=None, last_modified=None, author=None
        )
        vec_a = [0.1] * EMBEDDING_DIMENSIONS

        store.upsert_chunks(project_a, [chunk_a], [vec_a])
        
        # 2. Add data to Project B
        chunk_b = CodeChunk(
            id="b1", filename="file_b.py", start_line=1, end_line=1,
            content="def secret_b(): pass", type="function", language="python",
            symbol_name="secret_b", parent_symbol=None, signature=None, docstring=None, decorators=None, last_modified=None, author=None
        )
        vec_b = [0.9] * EMBEDDING_DIMENSIONS

        store.upsert_chunks(project_b, [chunk_b], [vec_b])
        
        # 3. Search Project A for 'secret'
        results_a = store.search(project_a, vec_a, limit=10)
        content_a = [r["content"] for r in results_a]
        
        assert "def secret_a(): pass" in content_a
        assert "def secret_b(): pass" not in content_a # ISOLATION CHECK
        
        # 4. Search Project B for 'secret'
        results_b = store.search(project_b, vec_b, limit=10)
        content_b = [r["content"] for r in results_b]
        
        assert "def secret_b(): pass" in content_b
        assert "def secret_a(): pass" not in content_b # ISOLATION CHECK
        
    finally:
        import shutil
        if Path("./test_vault_iso").exists():
            shutil.rmtree("./test_vault_iso")
        shutil.rmtree(project_a)
        shutil.rmtree(project_b)
