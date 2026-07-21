class LaspiLMException(Exception):
    """Base exception for LaspiLM."""
    pass

class PathNotFoundException(LaspiLMException):
    """Raised when a specified input path does not exist."""
    pass

class ParsingException(LaspiLMException):
    """Raised when Docling, MarkItDown or Tree-Sitter fails to parse a file."""
    pass

class StructuredOutputException(LaspiLMException):
    """Raised when the LLM fails to output valid JSON matching the Pydantic schema."""
    pass
