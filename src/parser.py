import os
import hashlib
from typing import List, Dict, Optional, Any
from pathlib import Path
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_html
import tree_sitter_css
import tree_sitter_json
import tree_sitter_markdown
import tree_sitter_yaml
import tree_sitter_sql
from tree_sitter import Language, Parser, Node

from .models import CodeChunk
from .config import SUPPORTED_EXTENSIONS

class CodeParser:
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}
        self._init_languages()

    def _init_languages(self):
        """Initialize Tree-sitter languages and parsers."""
        lang_map = {
            "python": tree_sitter_python,
            "javascript": tree_sitter_javascript,
            "typescript": tree_sitter_typescript,
            "tsx": tree_sitter_typescript,
            "html": tree_sitter_html,
            "css": tree_sitter_css,
            "json": tree_sitter_json,
            "yaml": tree_sitter_yaml,
            "sql": tree_sitter_sql,
        }

        self.ext_map = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "tsx", ".html": "html",
            ".css": "css", ".json": "json", ".yaml": "yaml",
            ".yml": "yaml", ".md": "markdown", ".sql": "sql"
        }

        for name, module in lang_map.items():
            try:
                # Direct calls to module.language() or specific language functions
                if name == "typescript" and hasattr(module, "language_typescript"):
                    lang = Language(module.language_typescript())
                elif name == "tsx" and hasattr(module, "language_tsx"):
                    lang = Language(module.language_tsx())
                elif hasattr(module, "language"):
                    lang = Language(module.language())
                else:
                    continue # Skip if no language function found
                
                self.languages[name] = lang
                self.parsers[name] = Parser(lang)
            except Exception:
                pass

    def parse_file(self, filepath: str) -> List[CodeChunk]:
        """Parses a file and returns semantic chunks."""
        ext = Path(filepath).suffix.lower()
        if ext not in getattr(self, 'ext_map', {}):
            return self._fallback_parse(filepath)

        lang_name = self.ext_map[ext]
        if lang_name not in self.parsers:
            return self._fallback_parse(filepath)

        parser = self.parsers[lang_name]
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            tree = parser.parse(bytes(content, "utf8"))
            chunks = self._chunk_node(tree.root_node, content, filepath, lang_name)
            
            # If no semantic chunks found, use fallback
            if not chunks:
                return self._fallback_parse(filepath)
            return chunks
        except Exception:
            return self._fallback_parse(filepath)

    def _fallback_parse(self, filepath: str) -> List[CodeChunk]:
        """Simple line-based chunking for unsupported files."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                content = "".join(lines)
            
            return [self._create_chunk(
                content,
                filepath,
                1,
                len(lines),
                "text_block",
                "text"
            )]
        except Exception:
            return []

    def _chunk_node(self, node: Node, full_content: str, filepath: str, lang_name: str) -> List[CodeChunk]:
        """Walks the AST and extracts meaningful chunks."""
        relevant_types = {
            "python": {"class_definition", "function_definition"},
            "javascript": {"class_declaration", "function_declaration", "method_definition", "arrow_function"},
            "typescript": {"class_declaration", "function_declaration", "method_definition", "interface_declaration", "enum_declaration"},
            "tsx": {"class_declaration", "function_declaration", "method_definition", "interface_declaration"},
            "go": {"function_declaration", "method_declaration", "type_declaration"},
        }
        
        target_types = relevant_types.get(lang_name, set())
        return self._recursive_chunk(node, full_content, filepath, lang_name, target_types)

    def _recursive_chunk(self, node: Node, content: str, filepath: str, lang: str, targets: set) -> List[CodeChunk]:
        chunks = []
        
        # Capture current node if it matches
        if node.type in targets:
            start_byte = node.start_byte
            end_byte = node.end_byte
            # Handle bytes decode/encode carefully
            # content is str.
            text = content.encode('utf-8')[start_byte:end_byte].decode('utf-8', errors='replace')
            
            chunk = self._create_chunk(
                text,
                filepath,
                node.start_point[0] + 1,
                node.end_point[0] + 1,
                node.type,
                lang
            )
            chunks.append(chunk)
            
            # Optimization: If we found a function, we usually don't need to chunk its internal if-statements 
            # as separate vector entries, the function body usually suffices. 
            # However, for Classes, we DO want methods.
            if "function" in node.type or "method" in node.type:
                return chunks 

        # Recursively checks children
        for child in node.children:
            chunks.extend(self._recursive_chunk(child, content, filepath, lang, targets))
            
        return chunks

    def _create_chunk(self, content: str, filename: str, start: int, end: int, type_: str, lang: str) -> CodeChunk:
        # Create a stable ID based on content and location
        raw_id = f"{filename}:{start}:{end}:{content}"
        chunk_id = hashlib.md5(raw_id.encode('utf-8')).hexdigest()
        
        return CodeChunk(
            id=chunk_id,
            filename=str(filename),
            start_line=start,
            end_line=end,
            content=content,
            type=type_,
            language=lang
        )
