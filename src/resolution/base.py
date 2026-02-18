from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

class ImportResolver(ABC):
    """
    Abstract base class for language-specific import resolution strategies.
    Responsible for mapping import strings (e.g. 'from .utils import foo')
    to physical file paths on disk.
    """

    def __init__(self):
        pass

    @abstractmethod
    def resolve(self, source_file: str, import_string: str, project_root: Optional[Path] = None) -> Optional[str]:
        """
        Resolves an import string to an absolute file path.
        
        Args:
            source_file: The absolute path of the file containing the import.
            import_string: The raw string from the import statement 
                           (e.g., "fastapi", "./utils", "package:flutter/material.dart").

        Returns:
            Absolute path to the resolved file, or None if resolution fails/is external.
        """
        pass
