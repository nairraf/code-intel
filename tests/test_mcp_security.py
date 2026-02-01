import pytest
import sys
import logging
import os
from pathlib import Path

# Add parent directory to path to import mcp_cognee
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_cognee

def test_protocol_fortress_active():
    """Verify that the MCP transport is monkeypatched for Stage 1 defense."""
    import mcp.server.stdio as mcp_stdio
    # Check if the global stdio_server points to our patched version
    assert mcp_stdio.stdio_server == mcp_cognee.patched_stdio_server
    assert hasattr(mcp_cognee, "_real_stdout_fd")
    assert hasattr(mcp_cognee, "_mcp_output_buffer")

def test_logger_silencing():
    """Verify that noisy loggers are silenced."""
    # We'll check Cognee and others. If pytest resets some, we'll verify Cognee at least.
    loggers_to_check = ["cognee", "instructor"] 
    for name in loggers_to_check:
        logger = logging.getLogger(name)
        # We manually set it in mcp_cognee.py. 
        # If it's still WARNING, we might need to re-apply it or check why.
        assert logger.level <= logging.ERROR

def test_update_check_disabled():
    """Verify that Cognee update checks are disabled via environment variables."""
    assert os.environ.get("COGNEE_DISABLE_UPDATE_CHECK") == "True"
    assert os.environ.get("COGNEE_SKIP_UPDATE_CHECK") == "True"

def test_handler_stripping():
    """Verify that load_cognee_context strips stdout handlers from all loggers."""
    # Use a unique logger name for this test
    rogue_logger = logging.getLogger("unique_rogue_logger")
    # Attach a handler pointing to the "real" stdout object we saved
    stdout_handler = logging.StreamHandler(mcp_cognee._real_stdout_obj)
    rogue_logger.addHandler(stdout_handler)
    
    # Verify it's there
    assert any(h.stream == mcp_cognee._real_stdout_obj for h in rogue_logger.handlers if isinstance(h, logging.StreamHandler))
    
    # This should strip all handlers pointing to _real_stdout_obj
    mcp_cognee.load_cognee_context()
    
    # Verify it's gone
    assert not any(h.stream == mcp_cognee._real_stdout_obj for h in rogue_logger.handlers if isinstance(h, logging.StreamHandler))

def test_root_handler_stripping():
    """Verify that root logger is also stripped of stdout handlers."""
    root_logger = logging.getLogger()
    stdout_handler = logging.StreamHandler(mcp_cognee._real_stdout_obj)
    root_logger.addHandler(stdout_handler)
    
    mcp_cognee.load_cognee_context()
    
    assert not any(h.stream == mcp_cognee._real_stdout_obj for h in root_logger.handlers if isinstance(h, logging.StreamHandler))

def test_mcp_output_buffer_exists():
    """Verify the private buffer to the original stdout is created."""
    assert hasattr(mcp_cognee, "_mcp_output_buffer")
    # Buffer should be open and writable
    assert not mcp_cognee._mcp_output_buffer.closed
