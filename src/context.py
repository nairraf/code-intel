"""
AppContext: Dependency Injection container for all shared services.

Centralises service instantiation so that:
  - Module-level side-effects (DB connections, HTTP clients) are deferred
    until first use rather than occurring at import time.
  - Tests can replace any service without monkey-patching module globals.

Usage
-----
  from src.context import get_context

  ctx = get_context()
  ctx.vector_store.search(...)

  # In tests: replace the singleton before calling the code under test.
  import src.context as _ctx
  _ctx._context = MyFakeContext()
"""

from .parser import CodeParser
from .embeddings import OllamaClient
from .storage import VectorStore
from .knowledge_graph import KnowledgeGraph
from .linker import SymbolLinker


class AppContext:
    """Container for all shared singleton services."""

    def __init__(self) -> None:
        self.parser = CodeParser()
        self.ollama = OllamaClient()
        self.vector_store = VectorStore()
        self.knowledge_graph = KnowledgeGraph()
        self.linker = SymbolLinker(self.vector_store, self.knowledge_graph)

    async def close(self) -> None:
        """Release any resources held by services (e.g. HTTP connections)."""
        await self.ollama.aclose()


# Module-level singleton — lazily initialised on first call to get_context().
_context: AppContext | None = None


def get_context() -> AppContext:
    """Return the process-wide AppContext, creating it on first call."""
    global _context
    if _context is None:
        _context = AppContext()
    return _context
