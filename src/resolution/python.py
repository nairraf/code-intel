import os
from pathlib import Path
from typing import Optional
from .base import ImportResolver

class PythonImportResolver(ImportResolver):
    """
    Resolves Python imports (absolute and relative) to file paths.
    Assumes standard project structure where imports are relative to project_root
    or site-packages (ignored for now).
    """
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root


    def resolve(self, source_file: str, import_string: str, project_root: Optional[Path] = None) -> Optional[str]:
        """
        Args:
            source_file: "/path/to/project/src/module.py"
            import_string: "src.utils" or ".utils" or ".."
            project_root: The project base directory
        """
        if project_root is None:
            if self.project_root:
                project_root = Path(self.project_root)
            else:
                return None
                
        source_path = Path(source_file)
        
        # 1. Handle Relative Imports (starting with .)
        resolved = None
        if import_string.startswith('.'):
            resolved = self._resolve_relative(source_path, import_string)
        else:
            # 2. Handle Absolute Imports
            resolved = self._resolve_absolute(project_root, import_string)
            
        if resolved and not self._is_within_root(resolved, project_root):
            return None
            
        return resolved

    def _resolve_relative(self, source_path: Path, import_string: str) -> Optional[str]:
        """
        Resolves relative imports like '.', '..', '.utils'.
        """
        # Count leading dots to determine level
        level = 0
        for char in import_string:
            if char == '.':
                level += 1
            else:
                break
        
        # Module name after dots (e.g. "utils" in ".utils")
        module_name = import_string[level:]
        
        # Determine base directory
        # If source is __init__.py, it is the package level.
        # If source is module.py, its parent is the package level.
        if source_path.name == '__init__.py':
            base_dir = source_path.parent
        else:
            base_dir = source_path.parent

        # Go up (level - 1) times for '..', but '.' is level 1 (current dir)
        # For 'from . import x', level=1. We want current dir.
        # For 'from .. import x', level=2. We want parent dir.
        try:
            for _ in range(level - 1):
                base_dir = base_dir.parent
        except ValueError:
            return None # Went above root

        if not module_name:
            # Import is just the package itself (e.g. "from . import x")
            # This usually resolves to __init__.py of that dir
            target = base_dir / "__init__.py"
            if target.exists():
                return str(target)
            return None

        # Import has a module part (e.g. ".utils")
        parts = module_name.split('.')
        current = base_dir
        
        # Traverse parts
        for i, part in enumerate(parts):
            # Check if it's a directory (package) or file (module)
            # If it's the last part, it could be a file or a package
            is_last = (i == len(parts) - 1)
            
            # Try package dir
            pkg_path = current / part
            # Try module file
            mod_path = current / f"{part}.py"
            
            if is_last:
                if mod_path.exists():
                    return str(mod_path)
                if pkg_path.exists() and (pkg_path / "__init__.py").exists():
                    return str(pkg_path / "__init__.py")
            else:
                # Must be a package directory to continue
                if pkg_path.exists():
                    current = pkg_path
                else:
                    return None
        
        return None

    def _resolve_absolute(self, project_root: Path, import_string: str) -> Optional[str]:
        """
        Resolves 'foo.bar' relative to project_root.
        """
        parts = import_string.split('.')
        current = project_root
        
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            
            pkg_path = current / part
            mod_path = current / f"{part}.py"
            
            if is_last:
                if mod_path.exists():
                    return str(mod_path)
                if pkg_path.exists() and (pkg_path / "__init__.py").exists():
                    return str(pkg_path / "__init__.py")
            else:
                if pkg_path.exists():
                    current = pkg_path
                else:
                    return None
                    
        return None
