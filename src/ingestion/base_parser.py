from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

class BaseParser(ABC):
    """Abstract interface for all document and code parsers."""
    
    @abstractmethod
    def parse(self, file_path: Path) -> Dict[str, Any]:
        """Parses the file and returns structured output."""
        pass
