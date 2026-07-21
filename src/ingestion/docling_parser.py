from pathlib import Path
from typing import Any, Dict
from src.ingestion.base_parser import BaseParser
from src.utils.exceptions import ParsingException
from src.utils.logger import logger
# pyrefly: ignore [missing-import]
# pyright: ignore [reportMissingImports]
from docling.document_converter import DocumentConverter

class DoclingParser(BaseParser):
    """Parser for PDF files using Docling to extract Markdown and metadata."""
    
    def __init__(self):
        try:
            self.converter = DocumentConverter()
        except Exception as e:
            logger.error(f"Falha ao inicializar DocumentConverter do Docling: {e}")
            raise
            
    def parse(self, file_path: Path) -> Dict[str, Any]:
        logger.debug(f"Parsing PDF via Docling: {file_path}")
        try:
            result = self.converter.convert(str(file_path))
            markdown_content = result.document.export_to_markdown()
            return {
                "source": str(file_path),
                "type": "document",
                "content": markdown_content
            }
        except Exception as e:
            logger.error(f"Erro no Docling ao parsear {file_path}: {e}")
            raise ParsingException(f"Failed to parse {file_path} with Docling: {e}")
