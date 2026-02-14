import httpx
import asyncio
import logging
from typing import List
from .config import EMBEDDING_ENDPOINT, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for fetching embeddings from a local Ollama instance."""
    
    def __init__(self, endpoint: str = EMBEDDING_ENDPOINT, model: str = EMBEDDING_MODEL):
        self.endpoint = endpoint
        self.model = model
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def get_embedding(self, text: str) -> List[float]:
        """Fetch embedding for a single text string with retry logic."""
        if not text.strip():
            return [0.0] * EMBEDDING_DIMENSIONS

        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.endpoint,
                        json={
                            "model": self.model,
                            "prompt": text,
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Ollama return format for /api/embeddings is usually {"embedding": [...]}
                    embedding = data.get("embedding")
                    
                    if not embedding:
                        raise ValueError(f"Ollama response missing 'embedding' field: {data}")
                    
                    if len(embedding) != EMBEDDING_DIMENSIONS:
                        logger.warning(
                            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, "
                            f"got {len(embedding)} for model {self.model}"
                        )
                    
                    return embedding

            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
                last_exception = e
                logger.warning(f"Ollama embedding attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        raise last_exception or Exception("Failed to get embedding after retries")

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Fetch embeddings for a list of strings (simple sequential implementation)."""
        # Note: Ollama /api/embeddings doesn't always support batching in all versions
        # so we do it sequentially or with gathered tasks for better performance.
        tasks = [self.get_embedding(text) for text in texts]
        return await asyncio.gather(*tasks)
