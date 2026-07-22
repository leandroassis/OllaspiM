import pytest
from unittest.mock import MagicMock, patch
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.generator import ReportGenerator

class DummyVectorStore:
    def get_retriever(self, collection_name, top_k=2, filters=None):
        mock_retriever = MagicMock()
        mock_node = MagicMock()
        mock_node.node.text = f"Contexto falso de {collection_name}"
        mock_retriever.retrieve.return_value = [mock_node]
        return mock_retriever

class DummyOllamaClient:
    def generate(self, prompt):
        return "termo1, termo2"
        
    def generate_structured(self, prompt, schema):
        schema_name = schema.__name__
        if schema_name == "AnalisePreliminar":
            return schema(analise_tecnica="Análise técnica mockada")
        return schema(status="Conforme", parecer_tecnico="O equipamento atende às especificações.")
@patch("src.rag.hybrid_retriever.nx.DiGraph")
@patch("src.rag.hybrid_retriever.HybridRetriever._load_graph")
def test_full_pipeline_generation(mock_load_graph, mock_digraph):
    # Setup mocks
    mock_load_graph.return_value = mock_digraph
    llm = DummyOllamaClient()
    store = DummyVectorStore()
    
    retriever = HybridRetriever("dummy.json", store, llm)
    # Sobrescreve métodos para evitar complexidade do grafo no teste
    retriever._get_topological_identifiers = MagicMock(return_value=["file1.py"])
    
    generator = ReportGenerator(retriever, llm_client=llm)
    parecer = generator.generate_parecer("EN-01", "Testar sobretemperatura.")
    
    assert "Status: Conforme" in parecer
    assert "atende às especificações" in parecer
