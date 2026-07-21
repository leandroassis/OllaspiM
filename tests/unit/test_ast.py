import pytest
from pathlib import Path
from src.ingestion.code_parser import CodeParser

def test_code_parser_unsupported_language(tmp_path):
    parser = CodeParser()
    test_file = tmp_path / "test.unknown"
    test_file.write_text("random content")
    
    res = parser.parse(test_file)
    assert res["functions"] == []
