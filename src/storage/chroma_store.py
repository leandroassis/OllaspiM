import chromadb
from typing import Any, Dict, List
from src.utils.logger import logger

from llama_index.core import VectorStoreIndex, Document, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

class ChromaStore:
    """Implementation of Vector Store using LlamaIndex over ChromaDB for legacy reports."""
    
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "legacy_reports"):
        self.persist_directory = persist_directory
        try:
            # Configuração Global do LlamaIndex para evitar fallback pro OpenAI
            Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
            Settings.llm = Ollama(model="qwen2.5:7b-instruct", request_timeout=120.0)
            Settings.chunk_size = 8192
            Settings.chunk_overlap = 5
            
            self.db = chromadb.PersistentClient(path=self.persist_directory)
            self.chroma_collection = self.db.get_or_create_collection(name=collection_name)
            self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
            self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            
            # Initialize index (can be empty at start)
            self.index = VectorStoreIndex.from_vector_store(
                self.vector_store, 
                storage_context=self.storage_context
            )
            logger.info(f"Conectado ao ChromaDB via LlamaIndex em {self.persist_directory}")
        except Exception as e:
            logger.error(f"Erro ao inicializar ChromaDB/LlamaIndex: {e}")
            raise
            
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Adds parsed legacy reports to LlamaIndex VectorStore."""
        if not documents:
            return
            
        llama_docs = []
        for doc in documents:
            llama_doc = Document(
                text=doc["content"], 
                doc_id=doc["id"], 
                metadata=doc.get("metadata", {})
            )
            llama_docs.append(llama_doc)
            
        try:
            for doc in llama_docs:
                self.index.insert(doc)
            logger.debug(f"Adicionados {len(documents)} documentos via LlamaIndex ao ChromaDB.")
        except Exception as e:
            logger.error(f"Erro ao adicionar documentos no LlamaIndex/ChromaDB: {e}")
            raise

    def get_retriever(self, top_k: int = 3):
        """Returns the LlamaIndex Native Retriever."""
        return self.index.as_retriever(similarity_top_k=top_k)
