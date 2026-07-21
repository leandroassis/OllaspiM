import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.ingestion.docling_parser import DoclingParser
from src.ingestion.markitdown_parser import MarkItDownParser

@patch("src.ingestion.docling_parser.DocumentConverter")
def test_docling_parser(mock_converter_class):
    mock_instance = MagicMock()
    mock_converter_class.return_value = mock_instance
    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "# Header\nContent"
    mock_instance.convert.return_value = mock_result
    
    parser = DoclingParser()
    res = parser.parse(Path("dummy.pdf"))
    
    assert res["type"] == "document"
    assert res["content"] == "# Header\nContent"
    assert res["source"] == "dummy.pdf"

@patch("src.ingestion.markitdown_parser.MarkItDown")
def test_markitdown_parser(mock_markitdown_class):
    mock_instance = MagicMock()
    mock_markitdown_class.return_value = mock_instance
    mock_result = MagicMock()
    mock_result.text_content = "Table Content"
    mock_instance.convert.return_value = mock_result
    
    parser = MarkItDownParser()
    res = parser.parse(Path("dummy.xlsx"))
    
    assert res["type"] == "table_office"
    assert res["content"] == "Table Content"
    assert res["source"] == "dummy.xlsx"
