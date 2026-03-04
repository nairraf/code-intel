import logging
from typing import Optional, Protocol
from tree_sitter import Node

logger = logging.getLogger(__name__)

class ScopingStrategy(Protocol):
    def is_global_target(self, node: Node) -> bool:
        """Determines if a variable/expression node is a top-level global."""
        ...

    def get_special_handling(self, node: Node) -> tuple[int, Node]:
        """
        Returns (adjusted_end_byte, adjusted_usage_node) for special cases.
        For example: merging dart function_signature + function_body.
        """
        ...

class DefaultScopingStrategy:
    def is_global_target(self, node: Node) -> bool:
        return False

    def get_special_handling(self, node: Node) -> tuple[int, Node]:
        return node.end_byte, node

class PythonScopingStrategy:
    def is_global_target(self, node: Node) -> bool:
        if node.type == "assignment":
            if node.parent and node.parent.type == "expression_statement":
                if node.parent.parent and node.parent.parent.type == "module":
                    return True
        elif node.type in ("expression_statement", "call"):
            curr = node
            while curr.parent:
                curr = curr.parent
            if curr.type == "module" and (node.parent.type == "module" if node.type == "expression_statement" else node.parent.type == "expression_statement" and node.parent.parent.type == "module"):
                return True
        return False

    def get_special_handling(self, node: Node) -> tuple[int, Node]:
        end_byte = node.end_byte
        usage_node = node
        if node.parent and node.parent.type == 'decorated_definition':
            usage_node = node.parent
        return end_byte, usage_node

class DartScopingStrategy:
    def is_global_target(self, node: Node) -> bool:
        if node.type in ("static_final_declaration_list", "initialized_identifier_list", "declaration"):
            if node.parent and node.parent.type == "program":
                return True
        elif node.type in ("expression_statement", "call"):
            if node.parent and (node.parent.type == "program" if node.type == "expression_statement" else node.parent.type == "expression_statement" and node.parent.parent and node.parent.parent.type == "program"):
                return True
        return False

    def get_special_handling(self, node: Node) -> tuple[int, Node]:
        end_byte = node.end_byte
        usage_node = node
        if node.type in ('function_signature', 'method_signature'):
            sib = node.next_named_sibling
            if sib and sib.type == 'function_body':
                end_byte = sib.end_byte
                usage_node = sib
        return end_byte, usage_node

def get_scoping_strategy(lang: str) -> ScopingStrategy:
    if lang == "python":
        return PythonScopingStrategy()
    elif lang == "dart":
        return DartScopingStrategy()
    return DefaultScopingStrategy()
