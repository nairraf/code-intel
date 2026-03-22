from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from ..utils import normalize_path

class ImportResolver(ABC):
    """
    Abstract base class for language-specific import resolution strategies.
    Responsible for mapping import strings (e.g. 'from .utils import foo')
    to physical file paths on disk.
    """

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

    @staticmethod
    def _is_within_root(resolved_path: str, project_root: Path) -> bool:
        """Ensures a resolved path stays within the project boundary."""
        try:
            normalized_resolved = normalize_path(resolved_path)
            normalized_root = normalize_path(str(project_root))
            return (
                normalized_resolved == normalized_root
                or normalized_resolved.startswith(f"{normalized_root}/")
            )
        except (ValueError, OSError, RuntimeError, TypeError):
            return False
