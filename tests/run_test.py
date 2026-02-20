import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server import refresh_index_impl, _find_definition
from src.config import EMBEDDING_DIMENSIONS

async def main():
    root = str(Path(__file__).parent / "mock_project")
    
    with patch("src.server.ollama_client") as mock:
        async def mock_emb(text):
            return [0.1] * EMBEDDING_DIMENSIONS
        async def mock_batch(texts, semaphore=None):
            return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]
        mock.get_embedding = AsyncMock(side_effect=mock_emb)
        mock.get_embeddings_batch = AsyncMock(side_effect=mock_batch)
        
        print(f"Indexing {root}...")
        res = await refresh_index_impl(root_path=root, force_full_scan=True)
        print(res)
        
        main_py_path = str(Path(root) / "main.py")
        print("\n--- Testing find_definition ---")
        def_res = await _find_definition(filename=main_py_path, line=4, symbol_name="verify_token", root_path=root)
        print(f"Definition Result:\n{def_res}")

if __name__ == "__main__":
    asyncio.run(main())
