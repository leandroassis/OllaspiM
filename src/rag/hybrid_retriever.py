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
        """Fase 2: Extrai termos-chave usando a LLM."""
        prompt = (
            f"Extraia os termos-chave mais importantes, nomes de arquivos, ou conceitos do seguinte texto.\n"
            f"Retorne APENAS uma lista de palavras separadas por vírgula.\n\nTexto: {text}"
        )
        res = self.llm.generate(prompt)
        return [t.strip() for t in res.split(",") if t.strip()]

    def _get_topological_identifiers(self, entities: List[str]) -> List[str]:
        """Fase 3: Consulta Topológica. Retorna lista de source_files restritos."""
        import re
        if not self.graph.nodes:
            return []
            
        root_nodes = set()
        entities_lower = [e.lower() for e in entities]
        
        # Busca de Raiz (Robust Substring Matching)
        for node, data in self.graph.nodes(data=True):
            node_text = (str(data.get("label", "")) + " " + str(data.get("properties", "")) + " " + str(node)).lower()
            
            for e in entities_lower:
                if e in node_text or node_text in e:
                    root_nodes.add(node)
                    break
                # Check individual words > 4 chars for robust morphological match
                e_words = [w for w in re.split(r'\W+', e) if len(w) > 4]
                n_words = [w for w in re.split(r'\W+', node_text) if len(w) > 4]
                if any(ew in nw or nw in ew for ew in e_words for nw in n_words):
                    root_nodes.add(node)
                    break
                
        # Travessia de Vizinhança (Profundidade 1 e 2)
        neighborhood = set(root_nodes)
        for root in root_nodes:
            # Vizinhos diretos e indiretos (undirected path logic for relatedness)
            undirected_G = self.graph.to_undirected()
            try:
                edges = nx.single_source_shortest_path_length(undirected_G, root, cutoff=2)
                for neighbor in edges.keys():
                    neighborhood.add(neighbor)
            except Exception:
                pass
                
        # Extração de Identificadores
        identifiers = set()
        for node in neighborhood:
            data = self.graph.nodes[node]
            source_file = data.get("source_file")
            # Fallback for ID if source_file not present but matches a file pattern
            if not source_file and str(node).count('.') > 0:
                source_file = str(node)
            if source_file:
                identifiers.add(source_file)
                
        logger.info(f"Fase 3 (Filtro Topológico): Encontrados {len(identifiers)} source_files restritivos na vizinhança: {list(identifiers)}")
        return list(identifiers)

    def retrieve_context(self, test_id: str, test_description: str) -> Tuple[str, str]:
        """
        Executa as Fases 2, 3 e 4 do pipeline híbrido sequencial.
        Retorna (project_context, legacy_context)
        """
        logger.info(f"Iniciando Recuperação Híbrida para: {test_description}")
        
        # Fase 2
        entities = self._extract_entities(test_description)
        logger.debug(f"Entidades extraídas: {entities}")
        
        # Fase 3
        identifiers = self._get_topological_identifiers(entities)
        
        # Fase 4: Recuperação Semântica com Restrição
        if not identifiers:
            logger.warning("Nenhum identificador encontrado no grafo. Tentando busca sem filtro restritivo.")
            filters = None
        else:
            filters = MetadataFilters(
                filters=[MetadataFilter(key="source_file", operator=FilterOperator.IN, value=identifiers)]
            )
            
        project_blocks = []
        for collection in ["documentation"]:
            try:
                retriever = self.vector_store.get_retriever(collection_name=collection, top_k=3, filters=filters)
                nodes = retriever.retrieve(test_description)
                if nodes:
                    source_files_found = [n.node.metadata.get('source_file', 'unknown') for n in nodes]
                    logger.info(f"Fase 4 (Projeto): {len(nodes)} chunks recuperados em '{collection}'. Arquivos: {source_files_found}")
                    
                    for i, n in enumerate(nodes):
                        logger.info(f"--- Chunk Recuperado ({collection}) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                    
                    block = f"--- {collection.upper()} ---\n"
                    # Format chunk tightly linking the source_file metadata
                    block += "\n\n".join([f"[Arquivo Origem: {n.node.metadata.get('source_file', 'desconhecido')}]\n{n.node.text}" for n in nodes])
                    project_blocks.append(block)
            except Exception as e:
                logger.error(f"Erro ao consultar coleção '{collection}': {e}")
                
        legacy_blocks = []
        # Legacy reports: search using test_id and entities to guarantee tight relevance
        query_legado = f"Ensaio ID: {test_id}. Entidades: {' '.join(entities)}. {test_description}"
        try:
            retriever_legacy = self.vector_store.get_retriever(collection_name="legacy_reports", top_k=3)
            legacy_nodes = retriever_legacy.retrieve(query_legado)
            if legacy_nodes:
                source_files_found = [n.node.metadata.get('source_file', 'unknown') for n in legacy_nodes]
                logger.info(f"Fase 4 (Legado): {len(legacy_nodes)} chunks recuperados com query '{query_legado[:50]}...'. Arquivos: {source_files_found}")
                
                for i, n in enumerate(legacy_nodes):
                    logger.info(f"--- Chunk Recuperado (Legado) [{n.node.metadata.get('source_file')}] ---\n{n.node.text[:300]}...")
                
                block = f"--- LEGACY_REPORTS ---\n"
                block += "\n\n".join([f"[Relatório Origem: {n.node.metadata.get('source_file', 'desconhecido')}]\n{n.node.text}" for n in legacy_nodes])
                legacy_blocks.append(block)
        except Exception as e:
            logger.error(f"Erro ao consultar coleção 'legacy_reports': {e}")
                
        project_context = "\n\n".join(project_blocks) if project_blocks else "Nenhum contexto técnico recuperado do projeto."
        legacy_context = "\n\n".join(legacy_blocks) if legacy_blocks else "Nenhum relatório histórico encontrado."
        
        return project_context, legacy_context
