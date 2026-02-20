import os
import pytest
from pathlib import Path
from src.utils import normalize_path

def test_normalize_path_basic():
    # Test simple relative path
    path = "src/server.py"
    normalized = normalize_path(path)
    assert normalized.endswith("src/server.py")
    assert "/" in normalized
    assert "\\" not in normalized
    assert Path(normalized).is_absolute()

def test_normalize_path_already_absolute():
    abs_path = str(Path("src/server.py").resolve())
    normalized = normalize_path(abs_path)
    assert normalized == Path(abs_path).as_posix().replace(Path(abs_path).as_posix()[0], Path(abs_path).as_posix()[0].lower(), 1) if os.name == 'nt' else Path(abs_path).as_posix()

def test_normalize_path_windows_casing():
    if os.name != 'nt':
        pytest.skip("Windows-specific test")
    
    # Simulate different casings of drive letter
    path1 = "C:/temp/file.txt"
    path2 = "c:/temp/file.txt"
    
    # normalize_path forces lowercase drive letter
    # and ensures absolute path (so C:/temp might become c:/me/Development/...)
    # Let's test with a real absolute path to be sure
    real_abs = str(Path(".").resolve())
    upper_abs = real_abs[0].upper() + real_abs[1:]
    lower_abs = real_abs[0].lower() + real_abs[1:]
    
    norm_upper = normalize_path(upper_abs)
    norm_lower = normalize_path(lower_abs)
    
    assert norm_upper == norm_lower
    assert norm_upper[0].islower()

def test_normalize_path_empty():
    assert normalize_path("") == ""
    assert normalize_path(None) == ""
