import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.search import (
    _classify_query_intent,
    _classify_result_type,
    _is_generated_artifact,
    _rank_results,
    search_code_impl,
)
from src.context import AppContext

from src.utils import normalize_path

@pytest.fixture(name="mock_ctx")
def mock_ctx_fixture():
    ctx = MagicMock(spec=AppContext)
    ctx.ollama = AsyncMock()
    ctx.vector_store = MagicMock()
    return ctx

@pytest.mark.asyncio
async def test_search_code_basic_success(mock_ctx):
    # Setup
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = [
        {
            "id": "1",
            "filename": "src/main.py",
            "start_line": 1,
            "end_line": 10,
            "content": "def hello(): pass",
            "symbol_name": "hello",
            "complexity": 1,
            "author": "Ian",
            "last_modified": "2026-03-04",
            "dependencies": "['os']"
        }
    ]
    
    # Execute
    test_path = "/proj"
    norm_path = normalize_path(test_path)
    result = await search_code_impl("hello", mock_ctx, root_path=test_path)
    
    # Assert
    assert f"Results for project: {norm_path}" in result
    assert "src/main.py (1-10)" in result
    assert "Symbol: hello" in result
    assert "Author: Ian" in result
    assert "Deps: ['os']" in result

@pytest.mark.asyncio
async def test_search_code_hybrid_keyword(mock_ctx):
    # Setup - query with a long keyword to trigger hybrid search
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = [] # No semantic results
    
    # Mock finding chunks by text (hybrid)
    mock_ctx.vector_store.find_chunks_containing_text.return_value = [
        {
            "id": "text_1",
            "filename": "src/ext.py",
            "start_line": 20,
            "end_line": 25,
            "content": "REALLYLONGKEYWORD = 1",
            "symbol_name": "REALLYLONGKEYWORD"
        }
    ]
    
    # Execute
    result = await search_code_impl("REALLYLONGKEYWORD", mock_ctx)
    
    # Assert
    assert "src/ext.py (20-25)" in result
    assert "REALLYLONGKEYWORD" in result
    mock_ctx.vector_store.find_chunks_containing_text.assert_called()

@pytest.mark.asyncio
async def test_search_code_filtering(mock_ctx):
    # Setup
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = [
        {"id": "1", "filename": "src/app.py", "start_line": 1, "end_line": 5, "content": "app", "symbol_name": "app"},
        {"id": "2", "filename": "tests/test_app.py", "start_line": 1, "end_line": 5, "content": "test", "symbol_name": "test"}
    ]
    
    # Execute with exclude
    result = await search_code_impl("app", mock_ctx, exclude="tests/**")
    
    # Assert
    assert "src/app.py" in result
    assert "tests/test_app.py" not in result

@pytest.mark.asyncio
async def test_search_code_no_results(mock_ctx):
    # Setup
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = []
    mock_ctx.vector_store.find_chunks_containing_text.return_value = []
    
    # Execute
    test_path = "/proj"
    norm_path = normalize_path(test_path)
    result = await search_code_impl("unknown", mock_ctx, root_path=test_path)
    
    # Assert
    assert f"No matching code found in project: {norm_path}" in result

@pytest.mark.asyncio
async def test_search_code_exception(mock_ctx):
    # Setup
    mock_ctx.ollama.get_embedding.side_effect = Exception("Ollama down")
    
    # Execute
    result = await search_code_impl("hello", mock_ctx)
    
    # Assert
    assert "Search failed: Ollama down" in result


def test_classify_query_intent_framework_query():
    assert _classify_query_intent("FastAPI router Depends middleware") == "framework"


def test_classify_result_type_report():
    assert _classify_result_type("docs/reports/security/report.md") == "report"


def test_is_generated_artifact_detects_generated_plugin_registrant():
    assert _is_generated_artifact("android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java")


def test_rank_results_preserves_semantic_order_over_complexity_for_same_result_type():
    results = [
        {
            "id": "1",
            "filename": "src/relevant.py",
            "symbol_name": "relevant_symbol",
            "complexity": 1,
            "start_line": 20,
            "_semantic_rank": 0,
        },
        {
            "id": "2",
            "filename": "src/noisy.py",
            "symbol_name": "noisy_symbol",
            "complexity": 10,
            "start_line": 10,
            "_semantic_rank": 1,
        },
    ]

    ranked = _rank_results(results, "implementation")

    assert ranked[0]["filename"] == "src/relevant.py"


@pytest.mark.asyncio
async def test_search_code_source_ranked_above_docs_for_implementation_query(mock_ctx):
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = [
        {
            "id": "doc1",
            "filename": "docs/architecture/auth.md",
            "start_line": 1,
            "end_line": 5,
            "content": "Authentication architecture overview",
            "symbol_name": None,
            "complexity": 0,
        },
        {
            "id": "src1",
            "filename": "src/auth_service.py",
            "start_line": 10,
            "end_line": 20,
            "content": "class AuthService: pass",
            "symbol_name": "AuthService",
            "complexity": 2,
        },
    ]
    mock_ctx.vector_store.find_chunks_containing_text.return_value = []

    result = await search_code_impl("authentication service implementation", mock_ctx, limit=2)

    assert result.index("File: src/auth_service.py") < result.index("File: docs/architecture/auth.md")
    assert "Result Type: source" in result
    assert "Query Intent: implementation" in result


@pytest.mark.asyncio
async def test_search_code_demotes_generated_artifacts_for_implementation_query(mock_ctx):
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = [
        {
            "id": "gen1",
            "filename": "android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java",
            "start_line": 1,
            "end_line": 30,
            "content": "public final class GeneratedPluginRegistrant {}",
            "symbol_name": "GeneratedPluginRegistrant",
            "complexity": 10,
            "_distance": 0.01,
        },
        {
            "id": "src1",
            "filename": "src/firebase_auth.py",
            "start_line": 1,
            "end_line": 20,
            "content": "def verify_firebase_token(): pass",
            "symbol_name": "verify_firebase_token",
            "complexity": 2,
            "_distance": 0.02,
        },
    ]
    mock_ctx.vector_store.find_chunks_containing_text.return_value = []

    result = await search_code_impl("JWT Firebase token validation middleware backend", mock_ctx, limit=2)

    assert result.index("File: src/firebase_auth.py") < result.index("File: android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java")


@pytest.mark.asyncio
async def test_search_code_limit_is_clamped(mock_ctx):
    mock_ctx.ollama.get_embedding.return_value = [0.1] * 1536
    mock_ctx.vector_store.search.return_value = []
    mock_ctx.vector_store.find_chunks_containing_text.return_value = []

    await search_code_impl("implementation service", mock_ctx, limit=999)

    _, kwargs = mock_ctx.vector_store.search.call_args
    assert kwargs["limit"] == 150
