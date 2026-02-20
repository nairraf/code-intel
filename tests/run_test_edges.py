import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server import refresh_index_impl
from src.storage import VectorStore
from src.knowledge_graph import KnowledgeGraph
from src.config import EMBEDDING_DIMENSIONS

async def main():
    root = str(Path(__file__).parent / "mock_project")
    print(f"Indexing {root}...")
    
    with patch("src.server.ollama_client") as mock:
        async def mock_emb(text): return [0.1] * EMBEDDING_DIMENSIONS
        async def mock_batch(texts, semaphore=None): return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]
        mock.get_embedding = AsyncMock(side_effect=mock_emb)
        mock.get_embeddings_batch = AsyncMock(side_effect=mock_batch)
        
        await refresh_index_impl(root_path=root, force_full_scan=True)
        
        v = VectorStore(str(Path(root) / "lancedb"))
        kg = KnowledgeGraph(str(Path(root) / "kg.sqlite"))
        
        print("TOTAL CHUNKS:", v.count_chunks(root))
        print("EDGES:", kg.get_edges())
        
        targets = v.find_chunks_by_symbol(root, "verify_token")
        print("FIND SYMBOL verify_token:", len(targets))
        if targets:
            print("  - File:", targets[0].get("filename"))

if __name__ == "__main__":
    asyncio.run(main())
