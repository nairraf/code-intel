import logging
from pathlib import Path
from typing import List, Optional
from .models import CodeChunk, SymbolUsage
from .knowledge_graph import KnowledgeGraph
from .resolution.python import PythonImportResolver
from .resolution.javascript import JSImportResolver
from .resolution.dart import DartImportResolver
from .storage import VectorStore

logger = logging.getLogger(__name__)

class SymbolLinker:
    def __init__(self, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.resolvers = {
            "python": PythonImportResolver(),
            "javascript": JSImportResolver(),
            "typescript": JSImportResolver(),
            "tsx": JSImportResolver(),
            "dart": DartImportResolver()
        }

    def link_chunk_usages(self, project_root: str, chunk: CodeChunk):
        """Resolves and links all usages within a chunk."""
        if not chunk.usages:
            return

        lang = chunk.language
        resolver = self.resolvers.get(lang)
        project_root_path = Path(project_root)
        
        for usage in chunk.usages:
            # 1. Try to find the target file
            target_file = None
            if resolver:
                # Basic resolution: check if it's an import-based resolution
                # (In a future phase, we'd extract the specific import string for this usage)
                pass
            
            # Heuristic: Search for symbol name in the project
            # In a more advanced version, we'd use the import context to narrow it down.
            targets = self.vector_store.find_chunks_by_symbol(project_root, usage.name)
            
            for target_chunk_dict in targets:
                target_id = target_chunk_dict.get("id")
                if target_id and target_id != chunk.id:
                    self.knowledge_graph.add_edge(
                        chunk.id, 
                        target_id, 
                        "call", 
                        {"context": usage.context, "line": usage.line}
                    )
                    # For now, we link to all potential candidates. 
                    # disambiguation comes later.
