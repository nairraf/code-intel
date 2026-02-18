from pydantic import BaseModel, Field
from typing import Optional, List

class SymbolUsage(BaseModel):
    """Represents a usage of a symbol (function call, instantiation, etc.)."""
    name: str = Field(..., description="The name of the symbol used (e.g. 'print', 'User')")
    line: int
    character: int
    context: str = "call"  # call, type_hint, instantiation, inheritance
    target_file: Optional[str] = None # Populated after resolution

class CodeChunk(BaseModel):
    """Represents a meaningful block of code (function, class, or text block)."""
    id: str = Field(..., description="Unique hash string of the chunk")
    filename: str
    start_line: int
    end_line: int
    content: str
    type: str = "text"  # e.g., "function", "class", "method", "text"
    language: str = "text"
    symbol_name: Optional[str] = None
    parent_symbol: Optional[str] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    decorators: Optional[List[str]] = None
    last_modified: Optional[str] = None
    author: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    related_tests: List[str] = Field(default_factory=list)
    usages: List[SymbolUsage] = Field(default_factory=list)
    complexity: int = 0
