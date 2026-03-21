import pytest
import os
import sys

# Fix sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import CodeParser

@pytest.fixture
def code_parser():
    return CodeParser()

def test_extract_python_usages(code_parser, tmp_path):
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
    
    chunks = code_parser.parse_file(str(f))
    
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

def test_extract_python_middleware_usages(code_parser, tmp_path):
    code = """
from fastapi import Depends

@verify_token
@app.get("/users")
def get_users(db = Depends(get_db_session)):
    pass
"""
    f = tmp_path / "test_middleware.py"
    f.write_text(code, encoding="utf-8")
    
    chunks = code_parser.parse_file(str(f))
    users_chunk = next(c for c in chunks if c.symbol_name == "get_users")
    
    usage_names = [u.name for u in users_chunk.usages]
    assert "verify_token" in usage_names
    assert "get" in usage_names  # app.get -> get
    assert "Depends" in usage_names
    assert "get_db_session" in usage_names

    db_session_usage = next(u for u in users_chunk.usages if u.name == "get_db_session")
    assert db_session_usage.context == "dependency_injection"


def test_extract_python_import_statement_usages(code_parser, tmp_path):
    code = """
from middleware.firebase_auth import verify_firebase_token as verify_token
"""
    f = tmp_path / "test_imports.py"
    f.write_text(code, encoding="utf-8")

    chunks = code_parser.parse_file(str(f))
    import_chunk = next(c for c in chunks if c.type == "import_from_statement")

    assert any(u.name == "verify_firebase_token" and u.context == "import" for u in import_chunk.usages)


def test_extract_python_override_registration_usage(code_parser, tmp_path):
    code = """
app.dependency_overrides[verify_firebase_token] = override_verify_firebase_token
"""
    f = tmp_path / "test_override.py"
    f.write_text(code, encoding="utf-8")

    chunks = code_parser.parse_file(str(f))
    assignment_chunk = next(c for c in chunks if c.type == "assignment")

    assert any(u.name == "verify_firebase_token" and u.context == "override_registration" for u in assignment_chunk.usages)

def test_extract_js_usages(code_parser, tmp_path):
    code = """
function main() {
    console.log("Hello");
    const user = new User();
    user.save();
}
"""
    f = tmp_path / "test.js"
    f.write_text(code, encoding="utf-8")
    
    chunks = code_parser.parse_file(str(f))
    main_chunk = next(c for c in chunks if c.symbol_name == "main")
    
    usage_names = [u.name for u in main_chunk.usages]
    assert "log" in usage_names # console.log -> log is property identifier
    assert "User" in usage_names
    assert "save" in usage_names
    
    # Check context for User (instantiation)
    user_usage = next(u for u in main_chunk.usages if u.name == "User")
    assert user_usage.context == "instantiation"

def test_extract_dart_usages(code_parser, tmp_path):
    code = """
class Processor {
  @override
  void process() {
    ref.watch(activeVisualThemeIdProvider);
    print('Processing');
    var data = fetchData();
    final user = User(name: 'Alice');
    final Widget w = MyWidget();
    final note = Note.fromFirestore(doc);
  }
}
"""
    f = tmp_path / "test.dart"
    f.write_text(code, encoding="utf-8")
    
    chunks = code_parser.parse_file(str(f))
    process_chunk = next(c for c in chunks if c.symbol_name == "process")
    
    usage_names = [u.name for u in process_chunk.usages]
    assert "print" in usage_names
    assert "fetchData" in usage_names
    assert "User" in usage_names
    assert "MyWidget" in usage_names
    assert "Widget" in usage_names
    assert "activeVisualThemeIdProvider" in usage_names
    assert "fromFirestore" in usage_names
