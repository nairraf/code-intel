import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.parser import CodeParser

def test_dart_parsing():
    parser = CodeParser()
    assert "dart" in parser.languages, "Dart language not initialized"
    
    dart_code = """
    import 'package:flutter/material.dart';

    // Top level function
    int add(int a, int b) {
      return a + b;
    }

    class MyWidget extends StatelessWidget {
      final String title;
      
      const MyWidget({required this.title});

      @override
      Widget build(BuildContext context) {
        return Text(title);
      }
      
      void _helper() => print("help");
    }
    """
    
    chunks = parser._chunk_node(
        parser.parsers['dart'].parse(bytes(dart_code, "utf8")).root_node,
        dart_code,
        "test.dart",
        "dart"
    )
    
    # Expected chunks:
    # 1. Top level function 'add' (signature + body merged)
    # 2. Class 'MyWidget' (wrapping everything)
    # 3. Method 'build' (signature + body merged)
    # 4. Method '_helper' (signature + body merged)
    # 5. Method 'MyWidget' (constructor) - usually method_signature or distinct?
    
    # We expect 4 or 5 chunks depending on constructor.
    # Let's inspect types.
    
    types = [c.type for c in chunks]
    print(f"Found types: {types}")
    
    # Check function merge
    add_func = next((c for c in chunks if "int add(int a, int b)" in c.content), None)
    assert add_func is not None
    assert "return a + b;" in add_func.content
    assert add_func.type == "function_signature"
    assert add_func.symbol_name == "add"

    # Check class
    class_def = next((c for c in chunks if c.type == "class_definition"), None)
    assert class_def is not None
    assert class_def.symbol_name == "MyWidget"
    assert class_def is not None
    assert "class MyWidget" in class_def.content
    
    # Check method merge
    build_method = next((c for c in chunks if "Widget build" in c.content), None)
    assert build_method is not None
    assert "return Text(title);" in build_method.content
    
    print("Dart parsing test passed!")

if __name__ == "__main__":
    test_dart_parsing()
