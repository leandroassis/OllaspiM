from typing import Tuple
from src.storage.chroma_store import ChromaStore
from src.utils.logger import logger

class VectorRetriever:
    """Implementa o RAG Vetorial direto, sem filtragem topológica."""
    
    def __init__(self, vector_store: ChromaStore, llm_client=None):
        self.vector_store = vector_store
        self.llm = llm_client
        
    def _extract_entities(self, text: str) -> str:
        """Extrai termos-chave usando a LLM para focar a busca vetorial."""
        if not self.llm:
            return text
            
        prompt = (
            f"Extraia os componentes, requisitos técnicos e palavras-chave fundamentais do seguinte texto.\n"
            f"Retorne APENAS uma lista curta de palavras-chave separadas por espaço.\n\nTexto: {text}"
        )
        try:
            res = self.llm.generate(prompt)
            # Tenta limpar separadores (vírgulas ou quebras de linha)
            res_clean = res.replace("\n", " ").replace(",", " ")
            keywords = " ".join([t.strip() for t in res_clean.split(" ") if t.strip()])
            if not keywords:
                keywords = text
            return keywords
        except Exception as e:
            logger.error(f"Erro ao extrair entidades: {e}")
            return text
        
    def retrieve_context(self, test_id: str, test_description: str, no_past: bool = False, num_chunks: int = 20, skip_extract_llm: bool = False) -> Tuple[str, str]:
        """
        Executa a busca vetorial com o requisito de entrada.
        Retorna (project_context, legacy_context)
        """
        logger.info(f"Iniciando Recuperação Vetorial Direta para: {test_id}")
        
        project_blocks = []
        try:
            if not skip_extract_llm and self.llm:
                search_query = self._extract_entities(test_description)
                logger.info(f"Keywords extraídas para busca: {search_query}")
            else:
                search_query = test_description
                logger.info(f"Busca direta sem extração (skip_extract_llm=True)")
                
            # Fase Projeto: Busca no ChromaDB
            retriever = self.vector_store.get_retriever(collection_name="documentation", top_k=num_chunks, filters=None)
            nodes = retriever.retrieve(search_query)
            
            if nodes:
                source_files_found = list(set([n.node.metadata.get('source_file', 'unknown') for n in nodes]))
                logger.info(f"Fase Projeto (Vetorial Direto): {len(nodes)} chunks recuperados. Arquivos: {source_files_found}")
                
                for i, n in enumerate(nodes):
                    logger.info(f"--- Chunk Recuperado (Projeto) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                
                block = f"--- DOCUMENTATION ---\n"
                formatted_nodes = []
                for n in nodes:
                    source_file = n.node.metadata.get('source_file', 'desconhecido')
                    parent_text = n.node.text
                    # Evidência bruta foi removida do contexto passado ao LLM
                    formatted_nodes.append(f"[Arquivo Origem: {source_file}]\n[Contexto Semântico]:\n{parent_text}")
                block += "\n\n".join(formatted_nodes)
                project_blocks.append(block)
        except Exception as e:
            logger.error(f"Erro ao consultar coleção 'documentation': {e}")
                
        legacy_blocks = []
        if not no_past:
            # Legacy reports: search using test_id and test_description natively
            query_legado = f"Ensaio ID: {test_id}. {test_description}"
            try:
                retriever_legacy = self.vector_store.get_retriever(collection_name="legacy_reports", top_k=3)
                legacy_nodes = retriever_legacy.retrieve(query_legado)
                if legacy_nodes:
                    source_files_found = [n.node.metadata.get('source_file', 'unknown') for n in legacy_nodes]
                    logger.info(f"Fase Legado: {len(legacy_nodes)} chunks recuperados. Arquivos: {source_files_found}")
                    
                    for i, n in enumerate(legacy_nodes):
                        logger.info(f"--- Chunk Recuperado (Legado) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                    
                    block = f"--- LEGACY_REPORTS ---\n"
                    formatted_nodes = []
                    for n in legacy_nodes:
                        source_file = n.node.metadata.get('source_file', 'desconhecido')
                        parent_text = n.node.text
                        formatted_nodes.append(f"[Relatório Origem: {source_file}]\n[Contexto Semântico]:\n{parent_text}")
                    block += "\n\n".join(formatted_nodes)
                    legacy_blocks.append(block)
            except Exception as e:
                logger.error(f"Erro ao consultar coleção 'legacy_reports': {e}")
        else:
            logger.info("Flag --no-past ativa. Ignorando contexto de relatórios históricos.")
                
        project_context = "\n\n".join(project_blocks) if project_blocks else "Nenhum contexto técnico recuperado do projeto."
        legacy_context = "\n\n".join(legacy_blocks) if legacy_blocks else "Nenhum relatório histórico encontrado."
        
        return project_context, legacy_context
