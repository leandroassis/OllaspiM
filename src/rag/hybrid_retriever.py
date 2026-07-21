from typing import Tuple
from src.storage.graphify_store import GraphifyKuzuStore
from src.storage.chroma_store import ChromaStore
from src.utils.logger import logger

class HybridRetriever:
    """Combines GraphRAG (rules/architecture) and VectorRAG (history/legacy) via LlamaIndex Retrievers."""
    
    def __init__(self, graph_store: GraphifyKuzuStore, vector_store: ChromaStore):
        self.graph_retriever = graph_store.get_retriever()
        self.vector_retriever = vector_store.get_retriever(top_k=3)
        
    def retrieve_context(self, test_description: str) -> Tuple[str, str]:
        """
        Executes hybrid retrieval natively using LlamaIndex Retrievers.
        """
        logger.info(f"Recuperando contexto via LlamaIndex para: {test_description}")
        
        # Fase 1: GraphRAG
        try:
            graph_nodes = self.graph_retriever.retrieve(test_description)
            graph_context = "\n".join([n.node.text for n in graph_nodes])
            logger.info(f"Conteúdo GraphRAG recuperado:\n{graph_context}")
        except Exception as e:
            logger.error(f"Erro no GraphRAG (LlamaIndex): {e}")
            graph_context = ""
            
        # Fase 2: VectorRAG
        try:
            vector_nodes = self.vector_retriever.retrieve(test_description)
            vector_context = "\n---\n".join([n.node.text for n in vector_nodes]) if vector_nodes else "Nenhum histórico encontrado."
            logger.info(f"Conteúdo VectorRAG recuperado:\n{vector_context}")
        except Exception as e:
            logger.error(f"Erro no VectorRAG (LlamaIndex): {e}")
            vector_context = ""
            
        return graph_context, vector_context
