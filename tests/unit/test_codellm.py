import pytest
from unittest.mock import patch, MagicMock
from src.llm.ollama_client import OllamaClient
from src.llm.schemas import CodeFunctionMetadata
from src.ingestion.code_enricher import CodeEnricher

@patch("src.llm.ollama_client.instructor.from_openai")
@patch("src.llm.ollama_client.OpenAI")
def test_ollama_client(mock_openai, mock_from_openai):
    mock_instructor_client = MagicMock()
    mock_from_openai.return_value = mock_instructor_client
    
    expected_response = CodeFunctionMetadata(
        nome_funcao="check_mancal_temp",
        arquivo="test.cpp",
        linhas="10-20",
        resumo_linguagem_natural="Test",
        logica_de_negocio=["Step 1"],
        condicoes_de_borda_e_limites="None",
        funcoes_chamadas=["read"],
        codigo_fonte_bruto="void check_mancal_temp() {}"
    )
    
    mock_instructor_client.chat.completions.create.return_value = expected_response
    
    client = OllamaClient()
    res = client.generate_structured("prompt", CodeFunctionMetadata)
    
    assert res.nome_funcao == "check_mancal_temp"
    assert res.arquivo == "test.cpp"

def test_code_enricher():
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = CodeFunctionMetadata(
        nome_funcao="mocked",
        arquivo="ignored",
        linhas="ignored",
        resumo_linguagem_natural="Resumo",
        logica_de_negocio=[],
        condicoes_de_borda_e_limites="",
        funcoes_chamadas=[],
        codigo_fonte_bruto="ignored"
    )
    
    enricher = CodeEnricher(llm_client=mock_llm)
    res = enricher.enrich_function("real_file.py", {"lines": "1-5", "codigo_fonte_bruto": "def a(): pass"})
    
    assert res.arquivo == "real_file.py"
    assert res.linhas == "1-5"
    assert res.codigo_fonte_bruto == "def a(): pass"
    assert res.nome_funcao == "mocked"
