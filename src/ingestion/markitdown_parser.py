from pathlib import Path
from typing import Any, Dict
from src.ingestion.base_parser import BaseParser
from src.utils.exceptions import ParsingException
from src.utils.logger import logger
from markitdown import MarkItDown

class MarkItDownParser(BaseParser):
    """Parser for Office and Table files using MarkItDown."""
    
    def __init__(self):
        try:
            self.markitdown = MarkItDown()
        except Exception as e:
            logger.error(f"Falha ao inicializar MarkItDown: {e}")
            raise
            
    def parse(self, file_path: Path) -> Dict[str, Any]:
        logger.debug(f"Parsing via MarkItDown: {file_path}")
        try:
            result = self.markitdown.convert(str(file_path))
            return {
                "source": str(file_path),
                "type": "table_office",
                "content": result.text_content
            }
        except Exception as e:
            logger.error(f"Erro no MarkItDown ao parsear {file_path}: {e}")
            raise ParsingException(f"Failed to parse {file_path} with MarkItDown: {e}")
