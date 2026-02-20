import pytest
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser

def test_mermaid_extraction(tmp_path):
    parser = CodeParser()
    code = """
Some markdown
```mermaid
graph TD;
    A[Start Node] --> B(End Node);
```
    """
    f = tmp_path / "test.md"
    f.write_text(code, encoding="utf-8")
    chunks = parser._extract_mermaid_chunks(code, str(f))
    # there should be blocks for Start Node and End Node
    assert len(chunks) >= 2
    assert any(c.type == "mermaid_node" and c.symbol_name == "A" for c in chunks)
    assert any(c.type == "mermaid_node" and c.symbol_name == "B" for c in chunks)

def test_python_parsing():
    parser = CodeParser()
    content = """
class MyClass:
    def method_one(self):
        pass

def global_function():
    return 42
"""
    # Create a temp file for testing
    test_file = Path("test_python.py")
    test_file.write_text(content, encoding='utf-8')
    
    try:
        chunks = parser.parse_file(str(test_file))
        assert len(chunks) == 3 # Class, method, and global function
        types = [c.type for c in chunks]
        assert "class_definition" in types
        assert "function_definition" in types
        # Check symbol_name and parent_symbol
        class_chunk = next(c for c in chunks if c.type == "class_definition")
        assert class_chunk.symbol_name == "MyClass"
        assert class_chunk.parent_symbol is None
        method_chunk = next(c for c in chunks if c.symbol_name == "method_one")
        assert method_chunk.parent_symbol == "MyClass"
        func_chunk = next(c for c in chunks if "global_function" in c.content)
        assert func_chunk.symbol_name == "global_function"
        assert func_chunk.parent_symbol is None
        assert "return 42" in func_chunk.content
        assert func_chunk.language == "python"
    finally:
        test_file.unlink()

def test_javascript_parsing():
    parser = CodeParser()
    content = """
class UIComponent {
    render() {
        return '<div></div>';
    }
}

const arrowFunc = () => {
    console.log("hello");
};
"""
    test_file = Path("test_js.js")
    test_file.write_text(content, encoding='utf-8')
    
    try:
        chunks = parser.parse_file(str(test_file))
        # Depending on tree-sitter grammars: class_declaration, method_definition, 
        # arrow_function (if supported as target)
        assert len(chunks) >= 2
        
        types = [c.type for c in chunks]
        assert any("class" in t for t in types)
        assert any("function" in t or "arrow" in t for t in types)
    finally:
        test_file.unlink()

def test_fallback_parsing():
    parser = CodeParser()
    content = "This is a plain text file\nwith some lines."
    test_file = Path("test_text.txt")
    test_file.write_text(content, encoding='utf-8')
    
    try:
        chunks = parser.parse_file(str(test_file))
        assert len(chunks) == 1
        assert chunks[0].type == "text_block"
        assert chunks[0].language == "text"
        assert chunks[0].content == content
    finally:
        test_file.unlink()
