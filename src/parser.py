
import sys
import builtins
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
import tree_sitter_language_pack as tslp

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
        # Standard bindings
        exact_map = {
            "python": tree_sitter_python,
            "javascript": tree_sitter_javascript,
            "typescript": tree_sitter_typescript,
            "html": tree_sitter_html,
            "css": tree_sitter_css,
            "json": tree_sitter_json,
            "yaml": tree_sitter_yaml,
            "sql": tree_sitter_sql,
        }

        # Extensions map
        self.ext_map = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "tsx", ".html": "html",
            ".css": "css", ".json": "json", ".yaml": "yaml",
            ".yml": "yaml", ".md": "markdown", ".sql": "sql",
            ".dart": "dart", ".go": "go", ".rs": "rust", 
            ".java": "java", ".cpp": "cpp", ".c": "c"
        }

        # Initialize standard bindings
        for name, module in exact_map.items():
            try:
                lang = Language(module.language())
                self.languages[name] = lang
                self.parsers[name] = Parser(lang)
            except Exception:
                pass

        # TypeScript special handling
        try:
            self.languages["tsx"] = Language(tree_sitter_typescript.language_tsx())
            self.parsers["tsx"] = Parser(self.languages["tsx"])
        except Exception:
            pass

        # Initialize from language pack (Dart, Go, Rust, etc.)
        pack_langs = ["dart", "go", "rust", "java", "cpp", "c"]
        for name in pack_langs:
            try:
                # get_language returns a tree_sitter.Language object directly
                lang = tslp.get_language(name)
                self.languages[name] = lang
                self.parsers[name] = Parser(lang)
            except Exception as e:
                # print(f"Failed to load {name}: {e}")
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
            "dart": {"class_definition", "function_signature", "method_signature"},
            "java": {"class_declaration", "method_declaration", "interface_declaration"},
            "rust": {"function_item", "impl_item", "trait_item", "macro_definition"},
            "cpp": {"function_definition", "class_specifier", "struct_specifier"},
        }
        target_types = relevant_types.get(lang_name, set())
        return self._recursive_chunk(node, full_content, filepath, lang_name, target_types, parent_name=None)

    def _recursive_chunk(self, node: Node, content: str, filepath: str, lang: str, targets: set, parent_name: Optional[str] = None) -> List[CodeChunk]:
        chunks = []
        # Capture current node if it matches
        if node.type in targets:
            start_byte = node.start_byte
            end_byte = node.end_byte
            # --- Dart Special Handling ---
            if lang == 'dart' and (node.type == 'function_signature' or node.type == 'method_signature'):
                sib = node.next_named_sibling
                if sib and sib.type == 'function_body':
                    end_byte = sib.end_byte
            text = content.encode('utf-8')[start_byte:end_byte].decode('utf-8', errors='replace')
            meta = self._extract_node_metadata(node, lang, content)
            chunk = self._create_chunk(
                text,
                filepath,
                node.start_point[0] + 1,
                node.end_point[0] + 1,
                node.type,
                lang,
                symbol_name=meta.get("symbol_name"),
                parent_symbol=parent_name,
                signature=meta.get("signature"),
                docstring=meta.get("docstring"),
                decorators=meta.get("decorators")
            )
            if lang == 'dart' and (node.type == 'function_signature' or node.type == 'method_signature'):
                sib = node.next_named_sibling
                if sib and sib.type == 'function_body':
                    chunk.end_line = sib.end_point[0] + 1
            chunks.append(chunk)
            # If it's a class-like node, recurse children with this class as parent
            if "class" in node.type or "impl" in node.type or "trait" in node.type:
                for child in node.children:
                    chunks.extend(self._recursive_chunk(child, content, filepath, lang, targets, parent_name=meta.get("symbol_name")))
                return chunks
            # If function/method, don't recurse into children
            if "function" in node.type or "method" in node.type:
                return chunks
        for child in node.children:
            chunks.extend(self._recursive_chunk(child, content, filepath, lang, targets, parent_name=parent_name))
        return chunks

    def _extract_node_metadata(self, node: Node, lang: str, content: str) -> dict:
        """Extract symbol_name, signature, docstring, and decorators from a tree-sitter node."""
        metadata = {
            "symbol_name": None,
            "signature": None,
            "docstring": None,
            "decorators": None,
        }
        # --- Symbol name ---
        name_node = node.child_by_field_name("name")
        if name_node:
            metadata["symbol_name"] = name_node.text.decode("utf-8", errors="replace")
        # --- Signature (functions/methods only) ---
        if "function" in node.type or "method" in node.type:
            parts = []
            if metadata["symbol_name"]:
                parts.append(metadata["symbol_name"])
            params_field = "parameters"
            if lang == "dart":
                params_field = "formal_parameter_list"
            params_node = node.child_by_field_name(params_field)
            if params_node:
                parts.append(params_node.text.decode("utf-8", errors="replace"))
            rt_field = "return_type"
            if lang == "go":
                rt_field = "result"
            elif lang in ("java", "dart"):
                rt_field = "type"
            rt_node = node.child_by_field_name(rt_field)
            if rt_node:
                parts.append("-> " + rt_node.text.decode("utf-8", errors="replace"))
            if parts:
                metadata["signature"] = " ".join(parts)
        # --- Docstring ---
        if lang == "python":
            body = node.child_by_field_name("body")
            if body and body.child_count > 0:
                first_stmt = body.children[0]
                if first_stmt.type == "expression_statement" and first_stmt.child_count > 0:
                    string_node = first_stmt.children[0]
                    if string_node.type == "string":
                        metadata["docstring"] = string_node.text.decode("utf-8", errors="replace").strip('"\' \n')
        else:
            prev = node.prev_named_sibling
            if prev and prev.type == "comment":
                metadata["docstring"] = prev.text.decode("utf-8", errors="replace").strip("/* \n")
        # --- Decorators ---
        decorator_types = {"decorator", "annotation", "attribute_item"}
        decorators_list = []
        prev = node.prev_named_sibling
        while prev and prev.type in decorator_types:
            decorators_list.insert(0, prev.text.decode("utf-8", errors="replace"))
            prev = prev.prev_named_sibling
        if decorators_list:
            metadata["decorators"] = decorators_list
        return metadata

    def _create_chunk(self, content: str, filename: str, start: int, end: int, type_: str, lang: str,
                      symbol_name=None, parent_symbol=None, signature=None, docstring=None, decorators=None) -> CodeChunk:
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
            language=lang,
            symbol_name=symbol_name,
            parent_symbol=parent_symbol,
            signature=signature,
            docstring=docstring,
            decorators=decorators
        )
