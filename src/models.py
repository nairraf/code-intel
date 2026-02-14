from pydantic import BaseModel, Field
from typing import Optional, List

class CodeChunk(BaseModel):
    """Represents a meaningful block of code (function, class, or text block)."""
    id: str = Field(..., description="Unique hash string of the chunk")
    filename: str
    start_line: int
    end_line: int
    content: str
    type: str = "text"  # e.g., "function", "class", "method", "text"
    language: str = "text"
