import pytest
import os
import sys
from pathlib import Path

# Fix sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser

@pytest.fixture
def parser():
    return CodeParser()

def test_extract_python_usages(parser, tmp_path):
    code = """
class MyClass:
    def method(self):
        print("Hello")
        self.helper()
        other_obj.do_something()

def helper():
    MyClass()
"""
    f = tmp_path / "test.py"
    f.write_text(code, encoding="utf-8")
    
    chunks = parser.parse_file(str(f))
    
    # helper chunk
    helper_chunk = next(c for c in chunks if c.symbol_name == "helper")
    assert any(u.name == "MyClass" and u.context == "call" for u in helper_chunk.usages)
    
    # MyClass.method chunk
    # Note: method chunk might be nested inside MyClass
    method_chunk = next(c for c in chunks if c.symbol_name == "method")
    usage_names = [u.name for u in method_chunk.usages]
    assert "print" in usage_names
    assert "helper" in usage_names
    assert "do_something" in usage_names

def test_extract_python_middleware_usages(parser, tmp_path):
    code = """
from fastapi import Depends

@verify_token
@app.get("/users")
def get_users(db = Depends(get_db_session)):
    pass
"""
    f = tmp_path / "test_middleware.py"
    f.write_text(code, encoding="utf-8")
    
    chunks = parser.parse_file(str(f))
    users_chunk = next(c for c in chunks if c.symbol_name == "get_users")
    
    usage_names = [u.name for u in users_chunk.usages]
    assert "verify_token" in usage_names
    assert "get" in usage_names  # app.get -> get
    assert "Depends" in usage_names
    assert "get_db_session" in usage_names

def test_extract_js_usages(parser, tmp_path):
    code = """
function main() {
    console.log("Hello");
    const user = new User();
    user.save();
}
"""
    f = tmp_path / "test.js"
    f.write_text(code, encoding="utf-8")
    
    chunks = parser.parse_file(str(f))
    main_chunk = next(c for c in chunks if c.symbol_name == "main")
    
    usage_names = [u.name for u in main_chunk.usages]
    assert "log" in usage_names # console.log -> log is property identifier
    assert "User" in usage_names
    assert "save" in usage_names
    
    # Check context for User (instantiation)
    user_usage = next(u for u in main_chunk.usages if u.name == "User")
    assert user_usage.context == "instantiation"

def test_extract_dart_usages(parser, tmp_path):
    code = """
class Processor {
  @override
  void process() {
    print('Processing');
    var data = fetchData();
    final user = User(name: 'Alice');
  }
}
"""
    f = tmp_path / "test.dart"
    f.write_text(code, encoding="utf-8")
    
    chunks = parser.parse_file(str(f))
    process_chunk = next(c for c in chunks if c.symbol_name == "process")
    
    usage_names = [u.name for u in process_chunk.usages]
    assert "print" in usage_names
    assert "fetchData" in usage_names
    # User constructor might vary slightly depending on grammar
    # usually constructor_name -> type_name -> type_identifier
    assert "User" in usage_names
