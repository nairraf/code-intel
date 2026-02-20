import pytest
import os
import sys

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Import directly from file names if package import fails
try:
    from server import _should_process_file
    from config import IGNORE_DIRS
except ImportError:
    # Fallback for when running from root
    from src.server import _should_process_file
    from src.config import IGNORE_DIRS

def test_should_process_file_defaults():
    root = "/project"
    # Standard file
    assert _should_process_file("/project/src/main.py", root, None, None) is True
    # System ignore
    assert _should_process_file("/project/venv/lib/site-packages/pkg/module.py", root, None, None) is False
    assert _should_process_file("/project/.git/HEAD", root, None, None) is False

def test_should_process_file_excludes():
    root = "/project"
    # Exclude tests
    assert _should_process_file("/project/tests/test_api.py", root, None, "tests/**") is False
    # Exclude specific file
    assert _should_process_file("/project/src/legacy.py", root, None, "src/legacy.py") is False
    # Exclude pattern vs Include (Exclude wins)
    assert _should_process_file("/project/src/bad.py", root, "src/**", "*.py") is False

def test_should_process_file_includes():
    root = "/project"
    # Include only src
    assert _should_process_file("/project/src/main.py", root, "src/**", None) is True
    assert _should_process_file("/project/docs/readme.md", root, "src/**", None) is False
    
    # Include specific extension
    assert _should_process_file("/project/src/main.py", root, "*.py", None) is True
    assert _should_process_file("/project/src/styles.css", root, "*.py", None) is False

def test_should_process_file_nested():
    root = "/project"
    # Deep nesting
    assert _should_process_file("/project/src/components/auth/login.py", root, "src/components/**", None) is True
    assert _should_process_file("/project/src/utils/helper.py", root, "src/components/**", None) is False
