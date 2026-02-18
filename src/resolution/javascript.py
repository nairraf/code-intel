import os
import json
import re
from pathlib import Path
from typing import Optional, Dict
from .base import ImportResolver

class JSImportResolver(ImportResolver):
    """
    Resolves JavaScript/TypeScript imports.
    Handles:
    - Relative imports (./, ../) with extension guessing (.js, .ts, .tsx, .jsx, .json)
    - Directory imports (index.js/ts)
    - Path aliases defined in tsconfig.json/jsconfig.json (e.g. @/ -> src/)
    """
    
    EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.json']
    
    
    def __init__(self):
        self._config_cache: Dict[str, tuple] = {} # root_path -> (aliases, base_url)
    
    def resolve(self, project_root: Path, source_file: str, import_string: str) -> Optional[str]:
        # 1. Handle Relative Imports
        if import_string.startswith('.'):
            return self._resolve_relative(source_file, import_string)
        
        # 2. Handle Path Aliases (e.g. @/components/Button)
        resolved = self._resolve_alias(project_root, import_string)
        if resolved:
            return resolved
            
        # 3. Handle Node Modules (Optimistic check for source code in node_modules)
        return None

    def _resolve_relative(self, source_file: str, import_string: str) -> Optional[str]:
        source_dir = Path(source_file).parent
        try:
            target_path = (source_dir / import_string).resolve()
            
            # Try direct file match (if extension provided)
            if target_path.exists() and target_path.is_file():
                return str(target_path)
                
            # Try adding extensions
            for ext in self.EXTENSIONS:
                p = target_path.with_suffix(ext)
                if p.exists():
                    return str(p)
                    
            # Try directory index
            if target_path.exists() and target_path.is_dir():
                for ext in self.EXTENSIONS:
                    p = target_path / f"index{ext}"
                    if p.exists():
                        return str(p)
        except Exception:
            pass
                        
        return None

    def _resolve_alias(self, project_root: Path, import_string: str) -> Optional[str]:
        """Resolves standard tsconfig path mapping."""
        path_aliases, base_url = self._get_config(project_root)
        if not path_aliases:
            return None
            
        for alias_pattern, target_patterns in path_aliases.items():
            # Standard exact match
            if alias_pattern == import_string:
                for target in target_patterns:
                    resolved = self._check_path_target(project_root, base_url, target)
                    if resolved: return resolved
            
            # Wildcard match (e.g. "@/*")
            if alias_pattern.endswith('*'):
                prefix = alias_pattern[:-1]
                if import_string.startswith(prefix):
                    suffix = import_string[len(prefix):]
                    for target in target_patterns:
                        if target.endswith('*'):
                            target_base = target[:-1]
                            potential_path = f"{target_base}{suffix}"
                            resolved = self._check_path_target(project_root, base_url, potential_path)
                            if resolved: return resolved
                            
        return None

    def _check_path_target(self, project_root: Path, base_url: str, target_rel_path: str) -> Optional[str]:
        """Checks if a target logic path exists on disk (with extensions)."""
        target_rel_path = target_rel_path.replace('/', os.sep)
        full_path = (project_root / base_url / target_rel_path).resolve()
        
        if full_path.exists() and full_path.is_file():
            return str(full_path)
            
        for ext in self.EXTENSIONS:
            p = full_path.with_suffix(ext)
            if p.exists():
                return str(p)
        
        if full_path.exists() and full_path.is_dir():
            for ext in self.EXTENSIONS:
                p = full_path / f"index{ext}"
                if p.exists():
                    return str(p)
                    
        return None

    def _get_config(self, project_root: Path) -> tuple:
        root_key = str(project_root)
        if root_key in self._config_cache:
            return self._config_cache[root_key]
            
        config = self._load_path_aliases(project_root)
        self._config_cache[root_key] = config
        return config

    def _load_path_aliases(self, project_root: Path) -> (Dict[str, list], str):
        config_files = ['tsconfig.json', 'jsconfig.json']
        for fname in config_files:
            config_path = project_root / fname
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        content = re.sub(r'//.*', '', content)
                        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                        
                        data = json.loads(content)
                        compiler_opts = data.get('compilerOptions', {})
                        paths = compiler_opts.get('paths', {})
                        base_url = compiler_opts.get('baseUrl', '.')
                        
                        return paths, base_url
                except Exception:
                    pass
        return {}, '.'
