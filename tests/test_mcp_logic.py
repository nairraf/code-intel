import pytest
import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
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

# ============================================================================
# IDENTITY TESTS
# ============================================================================

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
async def test_identity_malformed_package():
    """Test identity resolution with malformed package.json."""
    pkg = TEST_ROOT / "malformed_project"
    pkg.mkdir()
    with open(pkg / "package.json", "w") as f:
        f.write("{invalid json:}")

    # It should fall back to directory name
    p_id, _ = mcp_cognee.find_project_identity(str(pkg))
    assert p_id == "malformed_project"

# ============================================================================
# VAULT & LOGGING TESTS
# ============================================================================

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

    logging.getLogger("cognee").error("Test log message for isolation check")
    assert expected_log.exists()

    # Switch project
    other_dir = (TEST_ROOT / "node_project").resolve()
    p_id_2, _, _ = mcp_cognee.load_cognee_context(str(other_dir))
    expected_log_2 = central_logs / f"{p_id_2}.log"

    logging.getLogger("cognee").error("Test log message for isolation check project 2")
    assert expected_log_2.exists()

# ============================================================================
# NUCLEAR RESET TESTS
# ============================================================================

def test_nuclear_reset_removes_internals():
    """Verify _nuclear_reset removes .cognee_system and .data_storage."""
    vault = TEST_ROOT / "reset_test_vault"
    system_dir = vault / ".cognee_system" / "databases"
    data_dir = vault / ".data_storage" / "some_data"
    system_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (system_dir / "test.db").write_text("fake db")
    (data_dir / "chunk.json").write_text("{}")

    mcp_cognee._nuclear_reset(vault)

    assert not (vault / ".cognee_system").exists()
    assert not (vault / ".data_storage").exists()
    # Vault directory itself should still exist
    assert vault.exists()

def test_nuclear_reset_handles_missing():
    """Verify _nuclear_reset does not error on missing directories."""
    vault = TEST_ROOT / "empty_vault"
    vault.mkdir()
    # Should not raise
    mcp_cognee._nuclear_reset(vault)

# ============================================================================
# TOOL TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_tool_sync_offline():
    """Test sync tool when Ollama is offline."""
    with patch("mcp_cognee.check_ollama", return_value=False):
        result = await mcp_cognee.sync_project_memory.fn()
        assert "Ollama is not running" in result

@pytest.mark.asyncio
async def test_tool_search_offline():
    """Test search tool when Ollama is offline."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=False):
            result = await mcp_cognee.search_memory.fn("query")
            assert "Ollama offline" in result

@pytest.mark.asyncio
async def test_tool_sync_project_memory():
    """Test sync_project_memory tool with mocked cognee."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test_project", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("mcp_cognee._nuclear_reset"):
                with patch("cognee.config.system_root_directory"), \
                     patch("cognee.config.data_root_directory"):
                    with patch("cognee.add") as mock_add, patch("cognee.cognify") as mock_cognify:
                        # Create a fake file to find
                        (TEST_ROOT / "test.py").write_text("print('hello')")

                        result = await mcp_cognee.sync_project_memory.fn(str(TEST_ROOT))
                        assert "✅ Memory synced" in result
                        mock_add.assert_called_once()
                        mock_cognify.assert_called_once_with(chunks_per_batch=1)

@pytest.mark.asyncio
async def test_tool_sync_error():
    """Test sync tool error handling."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("mcp_cognee._nuclear_reset"):
                with patch("cognee.config.system_root_directory"), \
                     patch("cognee.config.data_root_directory"):
                    with patch("cognee.add", side_effect=Exception("Major failure")):
                        (TEST_ROOT / "data.py").write_text("x = 1")
                        result = await mcp_cognee.sync_project_memory.fn()
                        assert "Sync error: Major failure" in result

@pytest.mark.asyncio
async def test_tool_search_memory():
    """Test search_memory tool with mocked cognee."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test", TEST_ROOT, TEST_ROOT)):
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
    """Test prune_memory tool does nuclear reset."""
    with patch("mcp_cognee.load_cognee_context", return_value=("test_project", TEST_ROOT, TEST_ROOT)):
        with patch("mcp_cognee._nuclear_reset") as mock_reset:
            with patch("cognee.prune.prune_system"), patch("cognee.prune.prune_data"):
                result = await mcp_cognee.prune_memory.fn()
                assert "🧹 Memory pruned" in result
                mock_reset.assert_called_once_with(TEST_ROOT)

# ============================================================================
# CONTENT DEDUP TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_sync_deduplicates_identical_content():
    """Test that files with identical content at different paths are deduplicated."""
    dedup_root = TEST_ROOT / "dedup_project"
    dedup_root.mkdir()
    (dedup_root / ".git").mkdir()

    # Create two CSS files with IDENTICAL content at different paths
    dir_a = dedup_root / "docs" / "bible" / "net"
    dir_b = dedup_root / "docs" / "bible" / "webp"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)

    identical_content = "body { margin: 0; padding: 0; }"
    (dir_a / "haiola.css").write_text(identical_content)
    (dir_b / "haiola.css").write_text(identical_content)

    # Also create a file with different content
    (dedup_root / "main.py").write_text("print('unique')")

    with patch("mcp_cognee.load_cognee_context", return_value=("dedup_test", dedup_root, dedup_root)):
        with patch("mcp_cognee.check_ollama", return_value=True):
            with patch("mcp_cognee._nuclear_reset"):
                with patch("cognee.config.system_root_directory"), \
                     patch("cognee.config.data_root_directory"):
                    with patch("cognee.add") as mock_add, patch("cognee.cognify"):
                        result = await mcp_cognee.sync_project_memory.fn(str(dedup_root))

                        assert "✅ Memory synced" in result
                        # cognee.add should receive 2 files (one CSS + main.py), not 3
                        added_files = mock_add.call_args[0][0]
                        assert len(added_files) == 2
                        # The result message should mention the dedup count
                        assert "2 files" in result

# ============================================================================
# CONCURRENCY TESTS
# ============================================================================

def test_project_lock_isolation():
    """Verify that different projects get different locks."""
    lock_a = mcp_cognee._get_project_lock("project_a")
    lock_b = mcp_cognee._get_project_lock("project_b")
    lock_a2 = mcp_cognee._get_project_lock("project_a")

    assert lock_a is lock_a2  # Same project, same lock
    assert lock_a is not lock_b  # Different project, different lock

# ============================================================================
# EXTENSION COVERAGE TESTS
# ============================================================================

def test_dart_in_whitelist():
    """Verify .dart is included in whitelist extensions."""
    assert ".dart" in mcp_cognee.WHITELIST_EXTENSIONS

def test_skip_directories_complete():
    """Verify common noise directories are skipped."""
    for d in [".git", ".venv", "node_modules", "build", "__pycache__", ".dart_tool"]:
        assert d in mcp_cognee.SKIP_DIRECTORIES
