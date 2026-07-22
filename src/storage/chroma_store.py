import chromadb
from typing import Any, Dict, List
from src.utils.logger import logger

from llama_index.core import VectorStoreIndex, Document, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

class ChromaStore:
    """Implementation of Vector Store using LlamaIndex over ChromaDB for dynamic collections."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        try:
            # Configuração Global do LlamaIndex para evitar fallback pro OpenAI
            Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
            Settings.llm = Ollama(model="qwen2.5:7b-instruct", request_timeout=120.0)
            Settings.chunk_size = 8192
            Settings.chunk_overlap = 5
            
            self.db = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(f"Conectado ao ChromaDB em {self.persist_directory}")
        except Exception as e:
            logger.error(f"Erro ao inicializar ChromaDB: {e}")
            raise
            
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Adds parsed reports to corresponding LlamaIndex VectorStore collections."""
        if not documents:
            return
            
        # Agrupar por coleção
        collections_map = {}
        for doc in documents:
            col_name = doc.get("collection", "default")
            if col_name not in collections_map:
                collections_map[col_name] = []
            
            llama_doc = Document(
                text=doc["content"], 
                doc_id=doc["id"], 
                metadata=doc.get("metadata", {})
            )
            collections_map[col_name].append(llama_doc)
            
        for col_name, llama_docs in collections_map.items():
            try:
                chroma_collection = self.db.get_or_create_collection(name=col_name)
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                index = VectorStoreIndex.from_vector_store(
                    vector_store, 
                    storage_context=storage_context
                )
                
                from llama_index.core.node_parser import SentenceSplitter
                
                if col_name == "legacy_reports":
                    parser = SentenceSplitter(chunk_size=256, chunk_overlap=20)
                    nodes = parser.get_nodes_from_documents(llama_docs)
                    # No-Noise Policy: only index chunks that actually contain the final Parecer
                    nodes = [n for n in nodes if "parecer:" in n.text.lower()]
                else:
                    parser = SentenceSplitter(chunk_size=512, chunk_overlap=25)
                    nodes = parser.get_nodes_from_documents(llama_docs)
                    
                index.insert_nodes(nodes)
                logger.info(f"Adicionados {len(nodes)} chunks limpos (tam={parser.chunk_size}) para {len(llama_docs)} docs na coleção '{col_name}'.")
            except Exception as e:
                logger.error(f"Erro ao adicionar na coleção {col_name}: {e}")
                raise

    def get_retriever(self, collection_name: str, top_k: int = 3, filters: Any = None):
        """Returns the LlamaIndex Native Retriever for a specific collection with optional metadata filters."""
        chroma_collection = self.db.get_or_create_collection(name=collection_name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(
            vector_store, 
            storage_context=storage_context
        )
        return index.as_retriever(similarity_top_k=top_k, filters=filters)
