
import sys
import builtins
import httpx
import asyncio
import logging
from typing import List, Optional
from .config import EMBEDDING_ENDPOINT, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from .cache import EmbeddingCache

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for fetching embeddings from a local Ollama instance with caching."""

    def __init__(self, endpoint: str = EMBEDDING_ENDPOINT, model: str = EMBEDDING_MODEL):
        self.endpoint = endpoint
        self.model = model
        self.timeout = httpx.Timeout(60.0, connect=10.0)
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.cache = EmbeddingCache()

    async def aclose(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def get_embedding(self, text: str) -> List[float]:
        """Fetch embedding for a single text string with cache + retry logic."""
        # Check cache first
        cached_vector = self.cache.get(text, self.model)
        if cached_vector:
            logger.debug(f"Cache hit for text[:30]={text[:30]!r}")
            return cached_vector

        logger.debug(f"Cache miss for text[:30]={text[:30]!r}. Calling Ollama...")
        if not text.strip():
            logger.debug("Empty text received for embedding, returning zero vector.")
            return [0.0] * EMBEDDING_DIMENSIONS

        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    self.endpoint,
                    json={
                        "model": self.model,
                        "prompt": text,
                    }
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                
                if not embedding:
                    raise ValueError(f"Ollama response missing 'embedding' field: {data}")
                
                if len(embedding) != EMBEDDING_DIMENSIONS:
                    logger.warning(
                        f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, "
                        f"got {len(embedding)} for model {self.model}"
                    )
                
                # Cache the successful result
                self.cache.set(text, self.model, embedding)
                return embedding

            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
                last_exception = e
                logger.warning(f"Ollama embedding attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        logger.error(f"All embedding attempts failed for text[:30]={text[:30]!r}")
        raise last_exception or Exception("Failed to get embedding after retries")

    async def get_embeddings_batch(self, texts: List[str], semaphore: Optional[asyncio.Semaphore] = None) -> List[List[float]]:
        logger.debug(f"get_embeddings_batch called for {len(texts)} texts.")
        
        async def _bounded_get_embedding(text):
            if semaphore:
                async with semaphore:
                    return await self.get_embedding(text)
            return await self.get_embedding(text)

        tasks = [_bounded_get_embedding(text) for text in texts]
        results = await asyncio.gather(*tasks)
        logger.debug(f"get_embeddings_batch completed for {len(texts)} texts.")
        return results
