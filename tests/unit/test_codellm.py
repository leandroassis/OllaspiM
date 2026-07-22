import pytest
from unittest.mock import patch, MagicMock
from src.llm.ollama_client import OllamaClient
from src.ingestion.code_enricher import CodeEnricher

@patch("src.llm.ollama_client.OpenAI")
def test_ollama_client_generate(mock_openai):
    mock_raw_client = MagicMock()
    mock_openai.return_value = mock_raw_client
    mock_choice = MagicMock()
    mock_choice.message.content = "Mocked LLM Markdown Response"
    mock_raw_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    
    # Needs to patch instructor as well because __init__ uses it
    with patch("src.llm.ollama_client.instructor.from_openai"):
        client = OllamaClient()
        res = client.generate("prompt")
    
    assert res == "Mocked LLM Markdown Response"

def test_code_enricher():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Mocked Markdown Context"
    
    enricher = CodeEnricher(llm_client=mock_llm)
    res = enricher.enrich_function("real_file.py", {"lines": "1-5", "codigo_fonte_bruto": "def a(): pass", "name": "a"})
    
    assert "real_file.py" in res
    assert "1-5" in res
    assert "a" in res
    assert "Mocked Markdown Context" in res
