import chromadb
from typing import Any, Dict, List
from src.utils.logger import logger
from src.llm.ollama_client import OllamaClient

from llama_index.core import VectorStoreIndex, Document, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

class ChromaStore:
    """Implementation of Vector Store using LlamaIndex over ChromaDB for dynamic collections."""
    
    def __init__(self, persist_directory: str = "./chroma_db", token_budget: int = 512):
        self.persist_directory = persist_directory
        self.token_budget = token_budget
        self.llm_interpreter = OllamaClient(model="qwen2.5:7b-instruct")
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
                metadata=doc.get("metadata", {}),
                excluded_embed_metadata_keys=["raw_code"],
                excluded_llm_metadata_keys=["raw_code"]
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
                    parser = SentenceSplitter(chunk_size=self.token_budget, chunk_overlap=20)
                    nodes = parser.get_nodes_from_documents(llama_docs)
                    # The docling parser already trims the document to start at "Parecer:", 
                    # so all resulting chunks here belong to the relevant section.
                else:
                    parser = SentenceSplitter(chunk_size=self.token_budget, chunk_overlap=25)
                    nodes = parser.get_nodes_from_documents(llama_docs)
                    
                # --- NEW LLM INTERPRETATION STEP (SAR) ---
                for n in nodes:
                    doc_type = n.metadata.get("doc_type", "normative")
                    if doc_type == "normative":
                        prompt = f"Converta o seguinte texto bruto em uma dissertação técnica contínua (máx 3000 caracteres). Remova toda formatação markdown e artefatos de leitura (como cabeçalhos soltos ou tabelas quebradas). PRESERVE rigorosamente todos os fatos, valores numéricos, siglas e limites. NÃO resuma nem generalize o significado. Apenas transforme em prosa técnica clara e coesa:\n\n{n.text}"
                        try:
                            parent_text = self.llm_interpreter.generate(prompt)
                            n.metadata["raw_child_content"] = n.text
                            n.set_content(parent_text)
                        except Exception as e:
                            logger.warning(f"Erro ao gerar dissertação para chunk normativo: {e}")
                            n.metadata["raw_child_content"] = n.text
                    elif doc_type == "legacy":
                        prompt = f"Analise o seguinte fragmento de um relatório legado. Como o equipamento avaliado costuma ser caracterizado no contexto das verificações técnicas descritas aqui? Filtre dados administrativos irrelevantes e forneça uma descrição clara e alinhada focando nos aspectos técnicos (máx 3000 caracteres):\n\n{n.text}"
                        try:
                            parent_text = self.llm_interpreter.generate(prompt)
                            n.metadata["raw_child_content"] = n.text
                            n.set_content(parent_text)
                        except Exception as e:
                            logger.warning(f"Erro ao gerar dissertação para chunk legado: {e}")
                            n.metadata["raw_child_content"] = n.text
                    elif doc_type == "code_desc":
                        n.metadata["raw_child_content"] = n.metadata.get("raw_code", "Código original não disponível.")
                        
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
