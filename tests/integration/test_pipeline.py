import pytest
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.generator import ReportGenerator

class DummyRetriever:
    def __init__(self, nodes_text):
        self.nodes_text = nodes_text
    def retrieve(self, q):
        from llama_index.core.schema import NodeWithScore, TextNode
        return [NodeWithScore(node=TextNode(text=t), score=1.0) for t in self.nodes_text]

class DummyGraphStore:
    def add_document(self, doc_id, content, meta): pass
    def get_retriever(self):
        return DummyRetriever(["Subgrafo: Componente X conectado ao Sensor Y com limite 90C."])

class DummyVectorStore:
    def add_documents(self, docs): pass
    def get_retriever(self, top_k=5):
        return DummyRetriever(["Parecer Antigo: Equipamento aprovado sem ressalvas."])

class DummyOllamaClient:
    def generate_structured(self, prompt, schema):
        if schema.__name__ == "AnalisePreliminar":
            return schema(analise="Parecer preliminar: O componente possui limite de 90C.")
        return schema(status="Conforme", parecer_tecnico="O equipamento atende às especificações (90C).")

def test_full_pipeline_generation():
    retriever = HybridRetriever(DummyGraphStore(), DummyVectorStore())
    generator = ReportGenerator(retriever, llm_client=DummyOllamaClient())
    
    parecer = generator.generate_parecer("EN-01", "Testar sobretemperatura.")
    
    assert "Status: Conforme" in parecer
    assert "atende às especificações" in parecer
