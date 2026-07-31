import json
import networkx as nx
from typing import Tuple, List
from src.storage.chroma_store import ChromaStore
from src.llm.ollama_client import OllamaClient
from src.utils.logger import logger
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator

class HybridRetriever:
    """Implementa o RAG Híbrido baseado em Filtragem Topológica (Grafo restringe o Vetorial)."""
    
    def __init__(self, graph_json_path: str, vector_store: ChromaStore, llm_client: OllamaClient):
        self.graph_json_path = graph_json_path
        self.vector_store = vector_store
        self.llm = llm_client
        self.graph = self._load_graph()
        
    def _load_graph(self) -> nx.DiGraph:
        """Carrega o graph.json gerado pelo Graphify em um NetworkX DiGraph."""
        G = nx.DiGraph()
        try:
            with open(self.graph_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for node in data.get("nodes", []):
                nid = node.get("id")
                if nid:
                    G.add_node(nid, **node)
                    
            for edge in data.get("links", []):
                src = edge.get("source", edge.get("from"))
                tgt = edge.get("target", edge.get("to"))
                if src and tgt:
                    G.add_edge(src, tgt, **edge)
                    
            logger.info(f"Grafo carregado via NetworkX: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas.")
        except Exception as e:
            logger.error(f"Erro ao carregar grafo do Graphify: {e}")
        return G

    def _extract_entities(self, text: str) -> List[str]:
        """Fase 2a: Extrai termos-chave usando a LLM para evitar diluição na busca vetorial."""
        prompt = (
            f"Extraia os componentes, requisitos técnicos e nomes de testes fundamentais do seguinte objetivo.\n"
            f"Retorne APENAS uma lista curta de palavras-chave separadas por vírgula.\n\nObjetivo: {text}"
        )
        try:
            res = self.llm.generate(prompt)
            entities = [t.strip() for t in res.split(",") if t.strip()]
            return entities if entities else [text]
        except Exception as e:
            logger.error(f"Erro ao extrair entidades: {e}")
            return [text]

    def _get_seed_files(self, entities: List[str]) -> List[str]:
        """Fase Inicial (Vector): Multi-Query no ChromaDB para encontrar os source_files para cada entidade."""
        seed_files = set()
        try:
            for entity in entities:
                # Top 2 para CADA entidade independente
                retriever = self.vector_store.get_retriever(collection_name="documentation", top_k=2, filters=None)
                nodes = retriever.retrieve(entity)
                for n in nodes:
                    source_file = n.node.metadata.get("source_file")
                    if source_file:
                        seed_files.add(source_file)
            logger.info(f"Fase Semente (Vector Multi-Query): Encontrados {len(seed_files)} arquivos iniciais para {len(entities)} entidades: {list(seed_files)}")
        except Exception as e:
            logger.error(f"Erro na busca semente: {e}")
        return list(seed_files)

    def _expand_topology(self, seed_files: List[str]) -> List[str]:
        """Fase Intermediária (Graph): Expande a lista de arquivos via vizinhança e comunidades no Grafo."""
        if not self.graph.nodes or not seed_files:
            return seed_files
            
        seed_nodes = set()
        seed_communities = set()
        
        # 1. Identificar nós no grafo que correspondem aos seed_files
        for node, data in self.graph.nodes(data=True):
            source_file = data.get("source_file", "")
            node_id = str(node)
            
            # Checagem se o nó representa o arquivo semente
            if source_file in seed_files or any(sf in node_id for sf in seed_files):
                seed_nodes.add(node)
                community = data.get("community")
                if community is not None:
                    seed_communities.add(community)
                    
        logger.info(f"Fase Expansão (Graph): Identificados {len(seed_nodes)} nós raiz e comunidades {list(seed_communities)}.")
        
        # 2. Expandir: Pegar todos os nós da mesma comunidade e vizinhos diretos (Depth=1)
        expanded_nodes = set(seed_nodes)
        
        for node, data in self.graph.nodes(data=True):
            # Se for da mesma comunidade, puxa junto
            if data.get("community") in seed_communities:
                expanded_nodes.add(node)
                
        # Adicionar vizinhos diretos (1 pulo) dos nós raiz
        undirected_G = self.graph.to_undirected()
        for root in seed_nodes:
            try:
                edges = nx.single_source_shortest_path_length(undirected_G, root, cutoff=1)
                for neighbor in edges.keys():
                    expanded_nodes.add(neighbor)
            except Exception:
                pass
                
        # 3. Aplicar PageRank no Subgrafo Expandido para Filtrar a "Elite"
        subgraph = self.graph.subgraph(expanded_nodes)
        try:
            pr_scores = nx.pagerank(subgraph)
        except Exception as e:
            # Fallback for unconnected components or convergence issues
            pr_scores = {node: 1.0 for node in expanded_nodes}
            logger.warning(f"Erro ao computar PageRank: {e}")
            
        # Ordenar os nós pelo score de PageRank
        ranked_nodes = sorted(pr_scores.keys(), key=lambda n: pr_scores[n], reverse=True)
        
        # 4. Extrair os source_files da teia classificada (Limitando aos Top 10)
        expanded_files = set()
        
        # Sempre garantir que os arquivos semente originais estejam inclusos
        for sf in seed_files:
            expanded_files.add(sf)
            
        for node in ranked_nodes:
            if len(expanded_files) >= 10:
                break
                
            data = self.graph.nodes[node]
            source_file = data.get("source_file")
            if source_file:
                expanded_files.add(source_file)
            elif str(node).count('.') > 0:
                expanded_files.add(str(node))
                
        logger.info(f"Fase Expansão (Graph com PageRank): Teia classificada e filtrada para {len(expanded_files)} arquivos: {list(expanded_files)}")
        return list(expanded_files)

    def retrieve_context(self, test_id: str, test_description: str, no_past: bool = False, num_chunks: int = 20) -> Tuple[str, str]:
        """
        Executa o pipeline Vector -> Graph -> Vector.
        Retorna (project_context, legacy_context)
        """
        logger.info(f"Iniciando Recuperação Híbrida para: {test_id}")
        
        # Fase 2a: Multi-Query Entities
        entities = self._extract_entities(test_description)
        logger.debug(f"Fase Multi-Query Entidades: {entities}")
        
        # 1. Vector Search (Seed Multi-Query)
        seed_files = self._get_seed_files(entities)
        
        # 2. Graph Expansion
        identifiers = self._expand_topology(seed_files)
        
        # 3. Vector Search (Refined)
        if not identifiers:
            logger.warning("Nenhum identificador encontrado no grafo ou semente. Tentando busca sem filtro restritivo.")
            filters = None
        else:
            filters = MetadataFilters(
                filters=[MetadataFilter(key="source_file", operator=FilterOperator.IN, value=identifiers)]
            )
            
        project_blocks = []
        try:
            # Fase 4 (Refinada Multi-Query): Busca chunks iterando as entidades
            retriever = self.vector_store.get_retriever(collection_name="documentation", top_k=max(3, num_chunks // len(entities) + 1), filters=filters)
            
            all_project_nodes = {}
            for entity in entities:
                nodes = retriever.retrieve(entity)
                if nodes:
                    for n in nodes:
                        # Deduplicar chunks pelo texto
                        all_project_nodes[n.node.text] = n
                        
            if all_project_nodes:
                unique_nodes = list(all_project_nodes.values())[:num_chunks]
                source_files_found = list(set([n.node.metadata.get('source_file', 'unknown') for n in unique_nodes]))
                logger.info(f"Fase 4 (Projeto Refinado Multi-Query): {len(unique_nodes)}/{num_chunks} chunks recuperados. Arquivos: {source_files_found}")
                
                for i, n in enumerate(unique_nodes):
                    logger.info(f"--- Chunk Recuperado (Projeto) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                
                block = f"--- DOCUMENTATION ---\n"
                formatted_nodes = []
                for n in unique_nodes:
                    source_file = n.node.metadata.get('source_file', 'desconhecido')
                    parent_text = n.node.text
                    child_text = n.node.metadata.get('raw_child_content', 'Indisponível.')
                    formatted_nodes.append(f"[Arquivo Origem: {source_file}]\n[Contexto Semântico]:\n{parent_text}\n[Evidência Bruta para Citação]:\n{child_text}")
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
                    logger.info(f"Fase 4 (Legado): {len(legacy_nodes)} chunks recuperados. Arquivos: {source_files_found}")
                    
                    for i, n in enumerate(legacy_nodes):
                        logger.info(f"--- Chunk Recuperado (Legado) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                    
                    block = f"--- LEGACY_REPORTS ---\n"
                    formatted_nodes = []
                    for n in legacy_nodes:
                        source_file = n.node.metadata.get('source_file', 'desconhecido')
                        parent_text = n.node.text
                        child_text = n.node.metadata.get('raw_child_content', 'Indisponível.')
                        formatted_nodes.append(f"[Relatório Origem: {source_file}]\n[Contexto Semântico]:\n{parent_text}\n[Evidência Bruta para Citação]:\n{child_text}")
                    block += "\n\n".join(formatted_nodes)
                    legacy_blocks.append(block)
            except Exception as e:
                logger.error(f"Erro ao consultar coleção 'legacy_reports': {e}")
        else:
            logger.info("Flag --no-past ativa. Ignorando contexto de relatórios históricos.")
                
        project_context = "\n\n".join(project_blocks) if project_blocks else "Nenhum contexto técnico recuperado do projeto."
        legacy_context = "\n\n".join(legacy_blocks) if legacy_blocks else "Nenhum relatório histórico encontrado."
        
        return project_context, legacy_context
