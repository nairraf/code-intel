
import sys
import builtins
import os
import hashlib
import re
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

from tree_sitter import Language, Parser, Node, Query, QueryCursor

from .models import CodeChunk, SymbolUsage
from .config import SUPPORTED_EXTENSIONS
from .utils import normalize_path
from .parsers.firestore import FirestoreRulesParser

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
            ".java": "java", ".cpp": "cpp", ".c": "c",
            ".rules": "firestore"
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

    def parse_file(self, filepath: str, project_root: Optional[str] = None) -> List[CodeChunk]:
        """Parses a file and returns semantic chunks."""
        filepath = normalize_path(filepath)
        if project_root:
            project_root = normalize_path(project_root)
        
        ext = Path(filepath).suffix.lower()
        if ext not in getattr(self, 'ext_map', {}):
            return self._fallback_parse(filepath)

        lang_name = self.ext_map[ext]
        
        # Specialized parsers
        if lang_name == "firestore":
            return FirestoreRulesParser().parse(filepath)

        if lang_name not in self.parsers:
            return self._fallback_parse(filepath)

        parser = self.parsers[lang_name]
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            tree = parser.parse(bytes(content, "utf8"))
            
            # Extract file-level dependencies
            dependencies = self._extract_dependencies(tree.root_node, lang_name)
            
            # Find related tests
            related_tests = []
            if project_root:
                related_tests = self._find_related_tests(filepath, project_root)

            chunks = self._chunk_node(tree.root_node, content, filepath, lang_name)
            
            # If no semantic chunks found, use fallback
            if not chunks:
                chunks = self._fallback_parse(filepath)
            
            # Enrich chunks with file-level metadata
            for chunk in chunks:
                chunk.dependencies = dependencies
                chunk.related_tests = related_tests

            # Mermaid check for markdown
            if lang_name == "markdown":
                mermaid_chunks = self._extract_mermaid_chunks(content, filepath)
                chunks.extend(mermaid_chunks)

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
            "python": {"class_definition", "function_definition", "assignment"},
            "javascript": {"class_declaration", "function_declaration", "method_definition", "arrow_function"},
            "typescript": {"class_declaration", "function_declaration", "method_definition", "interface_declaration", "enum_declaration"},
            "tsx": {"class_declaration", "function_declaration", "method_definition", "interface_declaration"},
            "go": {"function_declaration", "method_declaration", "type_declaration"},
            "dart": {"class_definition", "function_signature", "method_signature", "method_declaration", "static_final_declaration_list", "initialized_identifier_list", "declaration"},
            "java": {"class_declaration", "method_declaration", "interface_declaration"},
            "rust": {"function_item", "impl_item", "trait_item", "macro_definition"},
            "cpp": {"function_definition", "class_specifier", "struct_specifier"},
        }
        target_types = relevant_types.get(lang_name, set())
        return self._recursive_chunk(node, full_content, filepath, lang_name, target_types, parent_name=None)

    def _recursive_chunk(self, node: Node, content: str, filepath: str, lang: str, targets: set, parent_name: Optional[str] = None) -> List[CodeChunk]:
        # print(f"[DEBUG] Visit: {node.type}")
        chunks = []
        # Capture current node if it matches
        if node.type in targets:
            # Scope Check: For assignments/declarations, only index if they are at the top level
            # python assignments are children of expression_statement, whose parent is module
            # dart declarations are direct children of program
            is_global = False
            if lang == "python" and node.type == "assignment":
                if node.parent and node.parent.type == "expression_statement":
                    if node.parent.parent and node.parent.parent.type == "module":
                        is_global = True
                if not is_global:
                    for child in node.children:
                        chunks.extend(self._recursive_chunk(child, content, filepath, lang, targets, parent_name=parent_name))
                    return chunks

            if lang == "dart" and node.type in ("static_final_declaration_list", "initialized_identifier_list", "declaration"):
                if node.parent and node.parent.type == "program":
                    is_global = True
                if not is_global:
                    for child in node.children:
                        chunks.extend(self._recursive_chunk(child, content, filepath, lang, targets, parent_name=parent_name))
                    return chunks

            # print(f"[DEBUG] Matched target: {node.type}")
            start_byte = node.start_byte
            end_byte = node.end_byte
            # --- Dart Special Handling ---
            usage_node = node
            if lang == 'dart' and (node.type == 'function_signature' or node.type == 'method_signature'):
                sib = node.next_named_sibling
                if sib and sib.type == 'function_body':
                    end_byte = sib.end_byte
                    usage_node = sib
            
            # --- Python Special Handling ---
            if lang == 'python' and node.parent and node.parent.type == 'decorated_definition':
                usage_node = node.parent
            
            text = content.encode('utf-8')[start_byte:end_byte].decode('utf-8', errors='replace')
            meta = self._extract_node_metadata(node, lang, content)
            usages = self._extract_usages(usage_node, lang)
            complexity = self._calculate_complexity(node)
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
                decorators=meta.get("decorators"),
                complexity=complexity,
                usages=usages
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
        if not name_node and lang == "dart":
            # Dart signatures might have name inside function_signature
            if node.type in ("method_signature", "method_declaration"):
                fs = next((c for c in node.children if c.type == "function_signature"), None)
                if fs:
                    name_node = fs.child_by_field_name("name")
            elif node.type == "function_signature":
                name_node = node.child_by_field_name("name")
            elif node.type == "static_final_declaration_list":
                # Find identifier in side static_final_declaration
                decl = next((c for c in node.children if c.type == "static_final_declaration"), None)
                if decl:
                    name_node = next((c for c in decl.children if c.type == "identifier"), None)
            elif node.type == "initialized_identifier_list":
                decl = next((c for c in node.children if c.type == "initialized_identifier"), None)
                if decl:
                    name_node = next((c for c in decl.children if c.type == "identifier"), None)
        
        if not name_node and lang == "python" and node.type == "assignment":
            name_node = node.child_by_field_name("left")
            if not name_node: # try first child identifier
                name_node = next((c for c in node.children if c.type == "identifier"), None)

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
                      symbol_name=None, parent_symbol=None, signature=None, docstring=None, 
                      decorators=None, complexity=0, usages=None) -> CodeChunk:
        # Create a stable ID based on content and location
        # Normalize line endings to prevent platform identity drift
        normalized_content = content.replace("\r\n", "\n")
        raw_id = f"{filename}:{start}:{end}:{normalized_content}"
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
            decorators=decorators,
            complexity=complexity,
            usages=usages or []
        )

    def _calculate_complexity(self, node: Node) -> int:
        """Calculates approximate Cyclomatic Complexity (1 + number of decisions)."""
        complexity_types = {
            "if_statement", "for_statement", "while_statement", "case_clause", 
            "catch_clause", "except_clause", "conditional_expression",
            "elif_clause", "for_in_statement"
        }
        
        def count_decisions(n):
            count = 0
            if n.type in complexity_types:
                count += 1
            if n.type == "binary_expression":
                op_node = n.child_by_field_name("operator")
                if op_node:
                    op_text = op_node.text.decode("utf-8", errors="replace").lower()
                    if op_text in ("&&", "||", "and", "or"):
                        count += 1
            for child in n.children:
                count += count_decisions(child)
            return count
        
        return 1 + count_decisions(node)

    def _extract_dependencies(self, root_node: Node, lang: str) -> List[str]:
        """Extracts import/using dependencies from the root node."""
        deps = set()
        language = self.languages.get(lang)
        if not language:
            return []

        if lang == "python":
            query = Query(language, """
                (import_statement (dotted_name) @name)
                (import_statement (aliased_import name: (dotted_name) @name))
                (import_from_statement module_name: (dotted_name) @name)
                (import_from_statement module_name: (relative_import) @name)
            """)
            captures = QueryCursor(query).captures(root_node)
            for tag, nodes in captures.items():
                for node in nodes:
                    deps.add(node.text.decode("utf-8", errors="replace"))
                
        elif lang == "dart":
            query = Query(language, "(string_literal) @path")
            captures = QueryCursor(query).captures(root_node)
            for tag, nodes in captures.items():
                for node in nodes:
                    # Check if any parent is import_or_export
                    p = node.parent
                    is_import = False
                    while p:
                        if p.type == "import_or_export":
                            is_import = True
                            break
                        p = p.parent
                    if is_import:
                        deps.add(node.text.decode("utf-8", errors="replace").strip("'\""))
        
        elif lang in ("javascript", "typescript", "tsx"):
            query = Query(language, """
                (import_statement source: (string) @path)
                (export_statement source: (string) @path)
            """)
            captures = QueryCursor(query).captures(root_node)
            for tag, nodes in captures.items():
                for node in nodes:
                    deps.add(node.text.decode("utf-8", errors="replace").strip("'\""))

        elif lang == "c#":
            query = Query(language, """
                (using_directive (identifier) @name)
                (using_directive (qualified_name) @name)
            """)
            captures = QueryCursor(query).captures(root_node)
            for tag, nodes in captures.items():
                for node in nodes:
                    deps.add(node.text.decode("utf-8", errors="replace"))
        
        return sorted(list(deps))

    def _find_related_tests(self, filepath: str, project_root: str) -> List[str]:
        """Heuristic to find test files related to the given source file."""
        related = []
        path_obj = Path(filepath)
        filename = path_obj.stem
        
        # Common test patterns
        patterns = [
            f"test_{filename}.py",
            f"{filename}_test.dart",
            f"{filename}.test.ts",
            f"{filename}.test.js",
            f"{filename}Tests.cs",
            f"Test{filename}.cs"
        ]
        
        # Local search (same directory)
        for p in patterns:
            test_file = path_obj.parent / p
            if test_file.exists():
                related.append(str(test_file.relative_to(project_root) if project_root else test_file))
        
        # Global search (tests/ or test/ directory)
        # We don't want to walk the whole project here for every file
        # But maybe we can check expected test directories
        test_roots = [Path(project_root) / "tests", Path(project_root) / "test"]
        for tr in test_roots:
            if tr.exists():
                for p in patterns:
                    # Heuristic: check if it exists in the test root with similar subpath
                    # For now just check direct existence in test root
                    if (tr / p).exists():
                        related.append(str((tr / p).relative_to(project_root) if project_root else (tr/p)))
                        
        return list(set(related))

    def _extract_usages(self, root_node: Node, lang: str) -> List[SymbolUsage]:
        """Extracts symbol usages (function calls, instantiations) from the node."""
        usages = []
        language = self.languages.get(lang)
        if not language:
            return []

        # Queries for usages
        queries = {
            "python": """
                (call function: (identifier) @name)
                (call function: (attribute attribute: (identifier) @name))
                (decorator (identifier) @name)
                (decorator (attribute attribute: (identifier) @name))
                (decorator (call function: (identifier) @name))
                (decorator (call function: (attribute attribute: (identifier) @name)))
                (call arguments: (argument_list (identifier) @name))
            """,
            "javascript": """
                (call_expression function: (identifier) @name)
                (call_expression function: (member_expression property: (property_identifier) @name))
                (new_expression constructor: (identifier) @name)
            """,
            "typescript": """
                (call_expression function: (identifier) @name)
                (call_expression function: (member_expression property: (property_identifier) @name))
                (new_expression constructor: (identifier) @name)
            """,
            "tsx": """
                (call_expression function: (identifier) @name)
                (call_expression function: (member_expression property: (property_identifier) @name))
                (new_expression constructor: (identifier) @name)
                (jsx_opening_element name: (identifier) @name) 
                (jsx_self_closing_element name: (identifier) @name)
            """,
            "dart": """
                (annotation name: (identifier) @name)
                ((identifier) @name . (selector))
            """
        }
        
        query_str = queries.get(lang)
        if not query_str:
            return []
            
        try:
            query = Query(language, query_str)
            captures = QueryCursor(query).captures(root_node)
            
            # Handle list of tuples (node, name) - standard tree-sitter
            if isinstance(captures, list):
                 for node, tag in captures:
                    name = node.text.decode("utf-8", errors="replace")
                    start_point = node.start_point
                    
                    context = "call"
                    if node.parent.type == "new_expression" or node.parent.type == "constructor_name":
                       context = "instantiation"
                    
                    usages.append(SymbolUsage(
                        name=name,
                        line=start_point[0] + 1,
                        character=start_point[1],
                        context=context
                    ))
            
            # Handle dict {name: [nodes]} - legacy/other bindings
            elif isinstance(captures, dict):
                for tag, nodes in captures.items():
                    for node in nodes:
                        name = node.text.decode("utf-8", errors="replace")
                        # Usage location
                        start_point = node.start_point
                        
                        # Context inference (simplified)
                        context = "call"
                        if node.parent.type == "new_expression" or node.parent.type == "constructor_name":
                           context = "instantiation"
                        
                        usages.append(SymbolUsage(
                            name=name,
                            line=start_point[0] + 1,
                            character=start_point[1],
                            context=context
                        ))
        except Exception:
            pass
            
        return usages

    def _extract_mermaid_chunks(self, content: str, filepath: str) -> List[CodeChunk]:
        """Extracts nodes from Mermaid blocks in Markdown as searchable chunks."""
        chunks = []
        # Find mermaid blocks
        mermaid_pattern = re.compile(r'```mermaid\s*(.*?)\s*```', re.DOTALL)
        
        # Node labels pattern: id["Label"], id(Label), id[Label], etc.
        node_pattern = re.compile(r'(\w+)(\[[^\]]+\]|\([^)]+\)|\{\{[^}]+\}\}|\[\[[^\]]+\]\]|\>[^\]]+\b\])')
        
        for m_match in mermaid_pattern.finditer(content):
            mermaid_code = m_match.group(1)
            offset = m_match.start(1)
            
            for n_match in node_pattern.finditer(mermaid_code):
                node_id = n_match.group(1)
                label = n_match.group(2).strip('[](){}>')
                
                # Calculate line number
                start_index = offset + n_match.start()
                start_line = content[:start_index].count('\n') + 1
                
                chunks.append(CodeChunk(
                    id=f"mermaid:{filepath}:{node_id}:{start_line}",
                    filename=filepath,
                    start_line=start_line,
                    end_line=start_line,
                    content=n_match.group(0),
                    type="mermaid_node",
                    language="mermaid",
                    symbol_name=node_id,
                    signature=f"Node {node_id} ({label})"
                ))
        return chunks
