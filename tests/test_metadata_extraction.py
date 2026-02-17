import pytest
from pathlib import Path
from src.parser import CodeParser

def test_python_dependencies():
    parser = CodeParser()
    content = """
import os
from pathlib import Path
import tree_sitter_python as tsp

def my_func():
    pass
"""
    test_file = Path("test_deps.py")
    test_file.write_text(content, encoding='utf-8')
    
    try:
        chunks = parser.parse_file(str(test_file))
        assert len(chunks) > 0
        deps = chunks[0].dependencies
        assert "os" in deps
        assert "pathlib" in deps
        assert "tree_sitter_python" in deps
    finally:
        test_file.unlink()

def test_complexity_calculation():
    parser = CodeParser()
    content = """
def complex_func(a, b):
    if a > b:
        return a
    elif b > a:
        for i in range(b):
            if i == a:
                return i
    return b
"""
    test_file = Path("test_complexity.py")
    test_file.write_text(content, encoding='utf-8')
    
    try:
        chunks = parser.parse_file(str(test_file))
        func_chunk = next(c for c in chunks if c.symbol_name == "complex_func")
        # if (1) + elif (1) + for (1) + if (1) + base (1) = 5
        assert func_chunk.complexity >= 5
    finally:
        test_file.unlink()

def test_related_tests_mapping(tmp_path):
    # Setup a mock project structure
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    src_dir = project_root / "src"
    src_dir.mkdir()
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    
    source_file = src_dir / "logic.py"
    source_file.write_text("def solve(): pass", encoding='utf-8')
    
    test_file = tests_dir / "test_logic.py"
    test_file.write_text("def test_solve(): pass", encoding='utf-8')
    
    parser = CodeParser()
    # We need to simulate the project_root passing from server.py
    chunks = parser.parse_file(str(source_file), project_root=str(project_root))
    
    assert len(chunks) > 0
    # The heuristic should find tests/test_logic.py
    assert any("test_logic.py" in t for t in chunks[0].related_tests)
