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
        
        # Pre-fetch potentially relevant symbols to minimize DB hits? 
        # No, for now let's query per usage as premature optimization might be complex.
        
        for usage in chunk.usages:
            targets = []
            
            # 1. Try Import Resolution (if available)
            if resolver and chunk.dependencies:
                # We need to know WHICH dependency imports this usage.
                # Current usages don't track which import they came from. 
                # We have to infer or check all dependencies.
                
                # Heuristic: Iterate through dependencies to see if we can resolve the symbol
                # This is O(N*M) where N=usages, M=deps. Usually small.
                for dep in chunk.dependencies:
                    # Construct potential import string? 
                    # For Python: "from module import Symbol" -> resolve("module") -> file?
                    # The dependency string in 'chunk.dependencies' is just the string found in code (e.g. "os", "src.utils")
                    
                    # Try to resolve the dependency string to a file path
                    resolved_path = resolver.resolve(chunk.filename, dep, project_root=project_root_path)
                    
                    if resolved_path:
                        # Normalize to POSIX for DB matching
                        resolved_path = Path(resolved_path).as_posix()
                        
                        # Check if the symbol exists in that file
                        # We need to query vector_store for "Symbol" in "resolved_path"
                        matches = self.vector_store.find_chunks_by_symbol_in_file(
                            project_root, 
                            usage.name, 
                            resolved_path
                        )
                        if matches:
                            # Tag as explicit/high confidence
                            for m in matches:
                                m["_match_type"] = "explicit_import"
                            targets.extend(matches)
            
            # 2. Heuristic: Search for symbol name globally (Fallback)
            if not targets:
                # Global search
                targets = self.vector_store.find_chunks_by_symbol(project_root, usage.name)
                for t in targets:
                    t["_match_type"] = "name_match"
            
            for target_chunk_dict in targets:
                target_id = target_chunk_dict.get("id")
                match_type = target_chunk_dict.get("_match_type", "unknown")
                
                # Avoid self-references (optional)
                if target_id and target_id != chunk.id:
                    self.knowledge_graph.add_edge(
                        chunk.id, 
                        target_id, 
                        "call", 
                        {
                            "context": usage.context, 
                            "line": usage.line,
                            "character": usage.character,
                            "match_type": match_type
                        }
                    )
