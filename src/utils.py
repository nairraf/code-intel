import os
from pathlib import Path

def normalize_path(path: str) -> str:
    """
    Returns a canonical absolute POSIX path.
    On Windows, it ensures the drive letter is consistently lowercased to 
    prevent hash/string mismatches in Database and Knowledge Graph.
    """
    if not path:
        return ""
    
    # 1. Resolve to absolute path
    p = Path(path).resolve()
    
    # 2. Get POSIX string
    path_str = p.as_posix()
    
    # 3. Handle Windows Drive Letter Casing
    # On Windows, Path.resolve() might return C:/ or c:/ depending on environment
    # We force lowercase for consistent hashing and lookups
    if os.name == 'nt' and len(path_str) > 1 and path_str[1] == ':':
        path_str = path_str[0].lower() + path_str[1:]
        
    return path_str
