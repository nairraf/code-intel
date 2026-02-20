import pytest
import os
import sys
import sqlite3
import pickle
from datetime import datetime, timedelta

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.cache import EmbeddingCache

@pytest.fixture
def temp_cache(tmp_path):
    db_path = tmp_path / "test_cache.db"
    return EmbeddingCache(db_path=str(db_path))

def test_cache_init(temp_cache):
    assert os.path.exists(temp_cache.db_path)
    # Verify table exists
    with sqlite3.connect(temp_cache.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'")
        assert cursor.fetchone() is not None

def test_cache_set_get(temp_cache):
    text = "hello world"
    model = "test-model"
    vector = [0.1, 0.2, 0.3]
    
    temp_cache.set(text, model, vector)
    result = temp_cache.get(text, model)
    
    assert result == vector

def test_cache_miss(temp_cache):
    assert temp_cache.get("non-existent", "model") is None

def test_cache_replace(temp_cache):
    text = "update me"
    model = "test-model"
    
    temp_cache.set(text, model, [1.0])
    temp_cache.set(text, model, [2.0])
    
    assert temp_cache.get(text, model) == [2.0]

def test_cache_operational_error_recovery(temp_cache):
    """Test that cache recovers if the table is manually dropped."""
    text = "recover"
    model = "test"
    temp_cache.set(text, model, [0.5])
    
    # Manually drop the table
    with sqlite3.connect(temp_cache.db_path) as conn:
        conn.execute("DROP TABLE embeddings")
        
    # Get should return None but re-init the DB
    assert temp_cache.get(text, model) is None
    
    # Set should work again
    temp_cache.set(text, model, [0.9])
    assert temp_cache.get(text, model) == [0.9]

def test_cache_prune(temp_cache, mocker):
    text_old = "old"
    text_new = "new"
    model = "test"
    
    # We need to manually insert an old record because 'set' uses current time
    db_path = temp_cache.db_path
    text_hash = temp_cache._compute_hash(text_old, model)
    old_date = datetime.utcnow() - timedelta(days=40)
    
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO embeddings (hash, vector, model, created_at, last_accessed) VALUES (?, ?, ?, ?, ?)",
            (text_hash, pickle.dumps([0.1]), model, old_date, old_date)
        )
    
    temp_cache.set(text_new, model, [0.2])
    
    # Prune items older than 30 days
    temp_cache.prune(days=30)
    
    assert temp_cache.get(text_old, model) is None
    assert temp_cache.get(text_new, model) == [0.2]
