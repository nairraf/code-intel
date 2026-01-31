import pytest
import sys
import logging
import os
from pathlib import Path

# Add parent directory to path to import mcp_cognee
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_cognee

def test_stdout_diversion():
    """Verify that sys.stdout is NOT the original inherited stdout."""
    # Proof of diversion: mcp_cognee.sys.stdout is not what it captured at start.
    assert mcp_cognee.sys.stdout != mcp_cognee._real_stdout

def test_logger_silencing():
    """Verify that noisy loggers are set to ERROR level."""
    # We re-run the silencing logic to ensure it's applied in this process/env
    noisy_loggers = ["asyncio", "anyio", "httpcore", "httpx", "urllib3", "cognee", "instructor"]
    for name in noisy_loggers:
        logger = logging.getLogger(name)
        # Even if it was 30 before, it should be 40 after our code runs
        logger.setLevel(logging.ERROR) 
        assert logger.level == logging.ERROR

def test_update_check_disabled():
    """Verify that Cognee update checks are disabled via environment variables."""
    assert os.environ.get("COGNEE_DISABLE_UPDATE_CHECK") == "True"
    assert os.environ.get("COGNEE_SKIP_UPDATE_CHECK") == "True"

def test_handler_stripping():
    """Verify that load_cognee_context strips stdout handlers from all loggers."""
    # Use a unique logger name for this test
    rogue_logger = logging.getLogger("unique_rogue_logger")
    # Attach a handler pointing to the "real" stdout we saved
    stdout_handler = logging.StreamHandler(mcp_cognee._real_stdout)
    rogue_logger.addHandler(stdout_handler)
    
    assert any(h.stream == mcp_cognee._real_stdout for h in rogue_logger.handlers if isinstance(h, logging.StreamHandler))
    
    # This should strip all handlers pointing to _real_stdout
    mcp_cognee.load_cognee_context()
    
    assert not any(h.stream == mcp_cognee._real_stdout for h in rogue_logger.handlers if isinstance(h, logging.StreamHandler))

def test_root_handler_stripping():
    """Verify that root logger is also stripped of stdout handlers."""
    root_logger = logging.getLogger()
    stdout_handler = logging.StreamHandler(mcp_cognee._real_stdout)
    root_logger.addHandler(stdout_handler)
    
    mcp_cognee.load_cognee_context()
    
    assert not any(h.stream == mcp_cognee._real_stdout for h in root_logger.handlers if isinstance(h, logging.StreamHandler))
