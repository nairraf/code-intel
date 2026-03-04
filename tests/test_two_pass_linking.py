
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server import refresh_index, find_references
from src.config import EMBEDDING_DIMENSIONS
from src.storage import VectorStore


@pytest.fixture
def mock_ollama():
    with patch("src.context._context.ollama") as mock:
        async def mock_emb(text):
            return [0.1] * EMBEDDING_DIMENSIONS

        async def mock_batch(texts, semaphore=None):
            return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]

        mock.get_embedding = AsyncMock(side_effect=mock_emb)
        mock.get_embeddings_batch = AsyncMock(side_effect=mock_batch)
        yield mock


@pytest.mark.asyncio
async def test_two_pass_linking_high_confidence(tmp_path, mock_ollama):
    """
    Verifies that a symbol defined in one file and used in another
    is correctly linked with High Confidence (explicit import).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()

    (project_root / "service.py").write_text(
        "class MyService:\n    def do_work(self):\n        pass", encoding="utf-8"
    )
    (project_root / "app.py").write_text(
        "from service import MyService\n\ndef main():\n    s = MyService()\n    s.do_work()",
        encoding="utf-8",
    )

    test_store = VectorStore(uri=str(tmp_path / "lancedb"))

    with patch("src.context._context.vector_store", test_store), \
         patch("src.context._context.linker.vector_store", test_store):
        result = await refresh_index.fn(root_path=str(project_root), force_full_scan=True)
        assert "Indexing Complete" in result

        refs = await find_references.fn(symbol_name="MyService", root_path=str(project_root))

        assert "Referenced in" in refs
        assert "app.py" in refs
        assert "High Confidence: explicit_import" in refs


@pytest.mark.asyncio
async def test_two_pass_linking_low_confidence(tmp_path, mock_ollama):
    """
    Verifies that a symbol used WITHOUT explicit import is linked
    with Low Confidence (name match).
    """
    project_root = tmp_path / "project_low"
    project_root.mkdir()

    (project_root / "utils.py").write_text("def helper(): pass", encoding="utf-8")
    (project_root / "script.py").write_text(
        "# no import\ndef main():\n    helper()", encoding="utf-8"
    )

    test_store = VectorStore(uri=str(tmp_path / "lancedb_low"))

    with patch("src.context._context.vector_store", test_store), \
         patch("src.context._context.linker.vector_store", test_store):
        await refresh_index.fn(root_path=str(project_root), force_full_scan=True)

        refs = await find_references.fn(symbol_name="helper", root_path=str(project_root))

        assert "Referenced in" in refs
        assert "script.py" in refs
        assert "Low Confidence: name_match" in refs
