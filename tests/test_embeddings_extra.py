import pytest
import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.embeddings import OllamaClient

@pytest.mark.asyncio
async def test_ollama_aclose():
    client = OllamaClient()
    # Replace the internal httpx client with a mock
    client.client = AsyncMock()
    await client.aclose()
    client.client.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_get_embedding_empty_text():
    client = OllamaClient()
    # Should return zero vector without calling Ollama
    client.client = AsyncMock()
    embedding = await client.get_embedding("   ")
    assert all(v == 0.0 for v in embedding)
    assert client.client.post.call_count == 0

@pytest.mark.asyncio
async def test_get_embeddings_batch_extra():
    client = OllamaClient()
    client.get_embedding = AsyncMock(return_value=[0.1, 0.2])
    
    texts = ["a", "b", "c"]
    results = await client.get_embeddings_batch(texts)
    
    assert len(results) == 3
    assert results[0] == [0.1, 0.2]
    assert client.get_embedding.call_count == 3

@pytest.mark.asyncio
async def test_get_embeddings_batch_with_semaphore():
    client = OllamaClient()
    client.get_embedding = AsyncMock(return_value=[0.5])
    
    sem = asyncio.Semaphore(2)
    texts = ["x", "y"]
    results = await client.get_embeddings_batch(texts, semaphore=sem)
    
    assert len(results) == 2
    assert client.get_embedding.call_count == 2
