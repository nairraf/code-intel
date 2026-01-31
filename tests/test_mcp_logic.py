import pytest
import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import logging

# Add parent directory to path to import mcp_cognee
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_cognee

# Setup a dummy environment for testing
TEST_ROOT = Path("test_env_sandbox")

@pytest.fixture(autouse=True)
def sandbox():
    """Setup and teardown the test sandbox."""
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir()
    
    # Create fake project structures
    (TEST_ROOT / "my_cool_project").mkdir()
    (TEST_ROOT / "my_cool_project" / ".git").mkdir()
    
    (TEST_ROOT / "flutter_project").mkdir()
    with open(TEST_ROOT / "flutter_project" / "pubspec.yaml", "w") as f:
        f.write("name: super_app\ndescription: a test app\n")

    (TEST_ROOT / "node_project").mkdir()
    with open(TEST_ROOT / "node_project" / "package.json", "w") as f:
        f.write('{"name": "mcp-web-tool", "version": "1.0.0"}')

    yield TEST_ROOT
    
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)

@pytest.mark.asyncio
async def test_identity_git():
    target_dir = (TEST_ROOT / "my_cool_project").resolve()
    with patch("os.getcwd", return_value=str(target_dir)):
        p_id, p_root = mcp_cognee.find_project_identity()
        assert p_id == "my_cool_project"
        assert p_root.resolve() == target_dir

@pytest.mark.asyncio
async def test_identity_flutter():
    target_dir = (TEST_ROOT / "flutter_project").resolve()
    with patch("os.getcwd", return_value=str(target_dir)):
        p_id, p_root = mcp_cognee.find_project_identity()
        assert p_id == "super_app"
        assert p_root.resolve() == target_dir.resolve()

@pytest.mark.asyncio
async def test_identity_node():
    target_dir = (TEST_ROOT / "node_project").resolve()
    with patch("os.getcwd", return_value=str(target_dir)):
        p_id, p_root = mcp_cognee.find_project_identity()
        assert p_id == "mcp-web-tool"
        assert p_root.resolve() == target_dir.resolve()

@pytest.mark.asyncio
async def test_identity_explicit_path():
    target_dir = (TEST_ROOT / "flutter_project").resolve()
    p_id, p_root = mcp_cognee.find_project_identity(str(target_dir))
    assert p_id == "super_app"
    assert p_root.resolve() == target_dir.resolve()

@pytest.mark.asyncio
async def test_vault_location():
    target_dir = (TEST_ROOT / "my_cool_project").resolve()
    p_id, p_vault, p_root = mcp_cognee.load_cognee_context(str(target_dir))
    assert p_root.resolve() == target_dir
    assert p_vault.resolve() == (target_dir / mcp_cognee.DEFAULT_VAULT_NAME).resolve()
    assert p_vault.exists()

@pytest.mark.asyncio
async def test_logging_isolation():
    target_dir = (TEST_ROOT / "flutter_project").resolve()
    p_id, p_vault, p_root = mcp_cognee.load_cognee_context(str(target_dir))
    
    central_logs = mcp_cognee._central_logs_dir
    expected_log = central_logs / f"{p_id}.log"
    
    # We log a message to trigger the file write
    logging.getLogger("cognee").error("Test log message for isolation check")
    assert expected_log.exists()
    
    # Switch project
    other_dir = (TEST_ROOT / "node_project").resolve()
    p_id_2, _, _ = mcp_cognee.load_cognee_context(str(other_dir))
    expected_log_2 = central_logs / f"{p_id_2}.log"
    
    logging.getLogger("cognee").error("Test log message for isolation check project 2")
    assert expected_log_2.exists()

@pytest.mark.asyncio
async def test_identity_malformed_package():
    """Test identity resolution with malformed package.json."""
    pkg = TEST_ROOT / "malformed_project"
    pkg.mkdir()
    with open(pkg / "package.json", "w") as f:
        f.write("{invalid json:}")
    
    # It should fall back to directory name
    p_id, _ = mcp_cognee.find_project_identity(str(pkg))
    assert p_id == "malformed_project"

@pytest.mark.asyncio
async def test_tool_sync_offline():
    """Test sync tool when Ollama is offline."""
    with patch("mcp_cognee.check_ollama", return_value=False):
        result = await mcp_cognee.sync_project_memory.fn()
        assert "Ollama is not running" in result

@pytest.mark.asyncio
async def test_tool_search_offline():
    """Test search tool when Ollama is offline."""
    with patch("mcp_cognee.load_cognee_context"):
        with patch("mcp_cognee.check_ollama", return_value=False):
            result = await mcp_cognee.search_memory.fn("query")
            assert "Ollama offline" in result

@pytest.mark.asyncio
async def test_tool_sync_error():
    """Test sync tool error handling."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("cognee.add", side_effect=Exception("Major failure")):
                # Add a dummy file to pass the "no valid files" check
                (TEST_ROOT / "data.py").write_text("x = 1")
                result = await mcp_cognee.sync_project_memory.fn()
                assert "Sync error: Major failure" in result

@pytest.mark.asyncio
async def test_prune_lock_deletion():
    """Test lock file deletion in prune_memory."""
    repo = TEST_ROOT / "repo"
    repo.mkdir()
    lock_dir = repo / ".cognee_vault" / ".cognee_system" / "databases" / "cognee_graph_kuzu"
    lock_dir.mkdir(parents=True)
    lock_file = lock_dir / ".lock"
    lock_file.write_text("locked")
    
    with patch("mcp_cognee.load_cognee_context", return_value=("repo", repo / ".cognee_vault", repo)):
        with patch("cognee.prune.prune_system"), patch("cognee.prune.prune_data"):
            await mcp_cognee.prune_memory.fn()
            assert not lock_file.exists()

@pytest.mark.asyncio
async def test_tool_sync_project_memory():
    """Test sync_project_memory tool with mocked cognee."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test_project", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("cognee.add") as mock_add, patch("cognee.cognify") as mock_cognify:
                # Create a fake file to find
                with open(TEST_ROOT / "test.py", "w") as f: f.write("print('hello')")
                
                result = await mcp_cognee.sync_project_memory.fn(str(TEST_ROOT))
                assert "✅ Memory synced" in result
                mock_add.assert_called_once()
                mock_cognify.assert_called_once_with(chunks_per_batch=1)

@pytest.mark.asyncio
async def test_tool_search_memory():
    """Test search_memory tool with mocked cognee."""
    with patch("mcp_cognee.load_cognee_context"):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("cognee.search", return_value=["result 1"]) as mock_search:
                result = await mcp_cognee.search_memory.fn("query")
                assert result == ["result 1"]
                mock_search.assert_called_once()

@pytest.mark.asyncio
async def test_tool_check_memory_status():
    """Test check_memory_status tool."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test_project", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            result = await mcp_cognee.check_memory_status.fn()
            assert result["project_identity"] == "test_project"
            assert result["ollama_status"] == "Online"

@pytest.mark.asyncio
async def test_tool_prune_memory():
    """Test prune_memory tool."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test_project", TEST_ROOT, TEST_ROOT)):
        with patch("cognee.prune.prune_system") as mock_sys, patch("cognee.prune.prune_data") as mock_data:
            result = await mcp_cognee.prune_memory.fn()
            assert "🧹 Memory pruned" in result
            mock_sys.assert_called_once()
            mock_data.assert_called_once()
