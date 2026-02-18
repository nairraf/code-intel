import pytest
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resolution.python import PythonImportResolver

# Mock project structure
@pytest.fixture
def mock_project(tmp_path):
    # Setup:
    # /project
    #   src/
    #     __init__.py
    #     main.py
    #     utils.py
    #     core/
    #       __init__.py
    #       engine.py
    #   tests/
    #     test_main.py
    
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    (project_root / "src").mkdir()
    (project_root / "src" / "__init__.py").touch()
    (project_root / "src" / "main.py").touch()
    (project_root / "src" / "utils.py").touch()
    
    (project_root / "src" / "core").mkdir()
    (project_root / "src" / "core" / "__init__.py").touch()
    (project_root / "src" / "core" / "engine.py").touch()
    
    (project_root / "tests").mkdir()
    (project_root / "tests" / "test_main.py").touch()
    
    return project_root

def test_resolve_absolute_import(mock_project):
    resolver = PythonImportResolver(str(mock_project))
    
    # from src.utils import foo
    resolved = resolver.resolve(
        source_file=str(mock_project / "src" / "main.py"),
        import_string="src.utils"
    )
    assert resolved == str(mock_project / "src" / "utils.py")

    # import src.core.engine
    resolved = resolver.resolve(
        source_file=str(mock_project / "src" / "main.py"),
        import_string="src.core.engine"
    )
    assert resolved == str(mock_project / "src" / "core" / "engine.py")

def test_resolve_relative_import_same_dir(mock_project):
    resolver = PythonImportResolver(str(mock_project))
    
    # from .utils import foo  (in src/main.py)
    resolved = resolver.resolve(
        source_file=str(mock_project / "src" / "main.py"),
        import_string=".utils"
    )
    # This should fail because relative imports need to be in a package?
    # Actually, main.py is in 'src' package if run as module.
    # But usually top-level scripts can do relative only with -m.
    # For static analysis, we assume structure.
    # Wait, 'src' has __init__.py, so it is a package.
    
    # The current implementation:
    # src/main.py -> parent is src/
    # .utils -> src/utils.py
    
    # Correction: `from . import utils` is typically `import_string='.'` and we resolve `utils` inside.
    # But tree-sitter might give us `.utils` if we parse `from .utils import foo`.
    # Let's assume input is `.utils`.
    
    assert resolved == str(mock_project / "src" / "utils.py")

def test_resolve_relative_import_parent_dir(mock_project):
    resolver = PythonImportResolver(str(mock_project))
    
    # from ..utils import foo  (in src/core/engine.py)
    # .. -> goes to src/
    # utils -> src/utils.py
    resolved = resolver.resolve(
        source_file=str(mock_project / "src" / "core" / "engine.py"),
        import_string="..utils"
    )
    assert resolved == str(mock_project / "src" / "utils.py")

def test_resolve_package_init(mock_project):
    resolver = PythonImportResolver(str(mock_project))
    
    # from src import core
    resolved = resolver.resolve(
        source_file=str(mock_project / "tests" / "test_main.py"),
        import_string="src.core"
    )
    assert resolved == str(mock_project / "src" / "core" / "__init__.py")

def test_resolve_external_import_returns_none(mock_project):
    resolver = PythonImportResolver(str(mock_project))
    
    # import os
    resolved = resolver.resolve(
        source_file=str(mock_project / "src" / "main.py"),
        import_string="os"
    )
    assert resolved is None
