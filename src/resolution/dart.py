import os
import re
from pathlib import Path
from typing import Optional
from .base import ImportResolver

class DartImportResolver(ImportResolver):
    """
    Resolves Dart imports.
    Handles:
    - Relative imports (import 'foo.dart', import '../foo.dart')
    - Package imports (import 'package:my_project/foo.dart' -> lib/foo.dart)
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root
        self._package_cache = {} # root_path -> package_name
    
    def resolve(self, source_file: str, import_string: str, project_root: Optional[Path] = None) -> Optional[str]:
        if project_root is None:
            if self.project_root:
                project_root = Path(self.project_root)
            else:
                return None
                
        # 1. Handle Package Imports
        resolved = None
        if import_string.startswith('package:'):
            resolved = self._resolve_package(project_root, import_string)

        # 2. Handle Relative Imports (usually start with ./ or ../ or just filename)
        elif not import_string.startswith('dart:'):
            resolved = self._resolve_relative(source_file, import_string)

        if resolved and not self._is_within_root(resolved, project_root):
            return None

        return resolved

    def _resolve_relative(self, source_file: str, import_string: str) -> Optional[str]:
        try:
            source_dir = Path(source_file).parent
            target_path = (source_dir / import_string).resolve()
            
            if target_path.exists() and target_path.is_file():
                return str(target_path)
        except Exception:
            pass
        
        return None

    def _resolve_package(self, project_root: Path, import_string: str) -> Optional[str]:
        package_name = self._get_package_data(project_root)
        if not package_name:
            return None
            
        prefix = f"package:{package_name}/"
        if import_string.startswith(prefix):
            rel_path = import_string[len(prefix):]
            full_path = (project_root / "lib" / rel_path).resolve()
            
            if full_path.exists() and full_path.is_file():
                return str(full_path)
        
        return None

    def _get_package_data(self, project_root: Path) -> Optional[str]:
        root_key = str(project_root)
        if root_key in self._package_cache:
            return self._package_cache[root_key]
            
        pkg_name = self._get_package_name(project_root)
        self._package_cache[root_key] = pkg_name
        return pkg_name

    def _get_package_name(self, project_root: Path) -> Optional[str]:
        pubspec_path = project_root / "pubspec.yaml"
        if not pubspec_path.exists():
            return None
            
        try:
            with open(pubspec_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'^name:\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None
