import pytest
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parsers.firestore import FirestoreRulesParser

def test_parse_firestore_simple(tmp_path):
    content = """
    service cloud.firestore {
      match /databases/{database}/documents {
        match /users/{userId} {
          allow read, write: if request.auth != null;
        }
      }
    }
    """
    rules_file = tmp_path / "firestore.rules"
    rules_file.write_text(content)
    
    parser = FirestoreRulesParser()
    chunks = parser.parse(str(rules_file))
    
    # Should find 2 matches: /databases/{database}/documents and /users/{userId}
    assert len(chunks) == 2
    assert any("/users/{userId}" in c.symbol_name for c in chunks)
    assert any("/databases/{database}/documents" in c.symbol_name for c in chunks)

def test_parse_firestore_nested_blocks(tmp_path):
    """Test correctly identifying the end of a block with nested braces."""
    content = """
    match /posts/{post} {
      allow write: if get(/$(path)).data.author == request.auth.uid;
      match /comments/{comment} {
        allow read: if true;
      }
    }
    """
    rules_file = tmp_path / "nested.rules"
    rules_file.write_text(content)
    
    parser = FirestoreRulesParser()
    chunks = parser.parse(str(rules_file))
    
    assert len(chunks) == 2
    
    # Content of the first chunk should include the second chunk
    first_chunk = next(c for c in chunks if "/posts/{post}" == c.symbol_name)
    assert "match /comments/{comment}" in first_chunk.content
    assert first_chunk.content.count("{") == first_chunk.content.count("}")

def test_parse_firestore_fallback(tmp_path):
    """Test that a file with no match blocks still returns a chunk."""
    content = "// Just some comments\nservice test {}"
    rules_file = tmp_path / "empty.rules"
    rules_file.write_text(content)
    
    parser = FirestoreRulesParser()
    chunks = parser.parse(str(rules_file))
    
    assert len(chunks) == 1
    assert chunks[0].type == "firestore_file"

def test_parse_firestore_error_handling():
    parser = FirestoreRulesParser()
    # Non-existent file
    assert parser.parse("non_existent_rules.rules") == []
