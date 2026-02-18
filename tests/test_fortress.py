import sys
import builtins
import pytest
import io

def test_print_redirection_to_stderr(mocker):
    # Tests assume safe_print is active. 
    # In tests, we must apply it explicitly.
    from src.server import safe_print
    mocker.patch("builtins.print", safe_print)
    
    # Capture stderr
    mock_stderr = io.StringIO()
    mocker.patch("sys.stderr", mock_stderr)
    
    # Call the patched print
    builtins.print("Fortress Test")
    
    # Check if it hit stderr
    output = mock_stderr.getvalue()
    assert "Fortress Test" in output

def test_explicit_file_print(mocker):
    # If someone tries to print to sys.stdout explicitly, it should still go to stderr
    from src.server import safe_print
    mocker.patch("builtins.print", safe_print)
    
    mock_stderr = io.StringIO()
    mocker.patch("sys.stderr", mock_stderr)
    
    builtins.print("Force Stdout", file=sys.stdout)
    
    output = mock_stderr.getvalue()
    assert "Force Stdout" in output

def test_original_print_preserved():
    # Verify we didn't lose the ability to print to real files if needed
    from src.server import _original_print, safe_print
    assert callable(_original_print)
    # This is a bit tricky to test if not run as __main__
    # but we can verify safe_print is distinct from _original_print
    assert _original_print != safe_print
