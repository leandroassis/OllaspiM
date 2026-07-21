import kuzu
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from src.utils.logger import logger
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode

class GraphifyKuzuStore:
    """Implementation of Graph Store using Graphify and KuzuDB."""
    
    def __init__(self, db_path: str = "./kuzu_db"):
        self.db_path = db_path
        self.staging_dir = Path(".graphify_input")
        self.out_dir = Path("graphify-out")
        
        # Ensure directories exist
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.db = kuzu.Database(self.db_path)
            self.conn = kuzu.Connection(self.db)
            self._init_schema()
            logger.info(f"Conectado ao KuzuDB em {self.db_path}")
        except Exception as e:
            logger.error(f"Erro ao conectar no KuzuDB: {e}")
            raise

    def _init_schema(self):
        """Initializes KuzuDB Node and Edge tables if they don't exist."""
        try:
            self.conn.execute("CREATE NODE TABLE Entity (id STRING, label STRING, file_type STRING, source_file STRING, properties STRING, PRIMARY KEY(id))")
        except Exception:
            pass  # Already exists
        
        try:
            self.conn.execute("CREATE REL TABLE RELATED_TO (FROM Entity TO Entity, relation STRING, properties STRING)")
        except Exception:
            pass

    def add_document(self, document_id: str, content: str, metadata: Dict[str, Any]):
        """Saves document content to staging directory for Graphify extraction."""
        # Clean path for safe writing, preserving structure if needed. For staging, basename is fine
        # if unique, but to avoid collisions, we replace slashes with underscores.
        safe_path = document_id.replace("/", "_").replace("\\", "_")
        
        # se for json do CodeLLM, salvar como .json
        try:
            # Tentar dar parse para ver se é JSON
            json.loads(content)
            # Se funcionou, é JSON
            ext = ".json"
        except json.JSONDecodeError:
            ext = ".md"
            
        if not safe_path.endswith(ext):
            safe_path += ext
            
        file_path = self.staging_dir / safe_path
        
        try:
            file_path.write_text(content, encoding='utf-8')
            logger.debug(f"Document {document_id} saved to staging: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save document to staging {file_path}: {e}")

    def build_graph(self):
        """Runs Graphify over the staging directory and ingests the result into KuzuDB."""
        logger.info("Executando extração do Graphify sobre os documentos e códigos em staging...")
        
        if not any(self.staging_dir.iterdir()):
            logger.warning("Nenhum arquivo no staging para rodar o Graphify.")
            return

        try:
            result = subprocess.run([
                sys.executable, "-m", "graphify", "extract", str(self.staging_dir),
                "--out", ".", "--backend", "ollama", "--model", "qwen2.5:7b-instruct",
                "--max-concurrency", "1"
            ], check=True, capture_output=True, text=True)
            logger.info("Extração do Graphify concluída com sucesso.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Falha ao executar graphify extract:\n{e.stderr}")
            raise
            
        # Graphify por padrão salva em graphify-out/graph.json
        graph_json_path = self.out_dir / "graph.json"
        if not graph_json_path.exists():
            logger.error(f"Arquivo {graph_json_path} não foi gerado pelo Graphify.")
            return
            
        logger.info(f"Ingerindo {graph_json_path} no KuzuDB...")
        try:
            with open(graph_json_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
        except Exception as e:
            logger.error(f"Falha ao ler graph.json: {e}")
            return
            
        nodes_pushed = 0
        edges_pushed = 0
        
        # Insert Nodes
        for node in graph_data.get("nodes", []):
            nid = node.get("id")
            if not nid:
                continue
            
            label = node.get("label", "Entity")
            ftype = node.get("file_type", "")
            sf = node.get("source_file", "")
            
            props = {k: v for k, v in node.items() if k not in ("id", "label", "file_type", "source_file")}
            props_str = json.dumps(props)
            
            query = """
            MERGE (n:Entity {id: $id}) 
            ON MATCH SET n.label = $label, n.file_type = $ftype, n.source_file = $sf, n.properties = $props 
            ON CREATE SET n.label = $label, n.file_type = $ftype, n.source_file = $sf, n.properties = $props
            """
            self.conn.execute(query, {"id": str(nid), "label": str(label), "ftype": str(ftype), "sf": str(sf), "props": props_str})
            nodes_pushed += 1
            
        # Insert Edges
        for edge in graph_data.get("edges", []):
            src = edge.get("source", edge.get("from"))
            tgt = edge.get("target", edge.get("to"))
            rel = edge.get("relation", "RELATED_TO")
            
            if not src or not tgt:
                continue
                
            props = {k: v for k, v in edge.items() if k not in ("source", "target", "from", "to", "relation")}
            props_str = json.dumps(props)
            
            query = """
            MATCH (a:Entity {id: $src}), (b:Entity {id: $tgt}) 
            MERGE (a)-[r:RELATED_TO {relation: $rel}]->(b) 
            ON MATCH SET r.properties = $props 
            ON CREATE SET r.properties = $props
            """
            self.conn.execute(query, {"src": str(src), "tgt": str(tgt), "rel": str(rel), "props": props_str})
            edges_pushed += 1
            
        logger.info(f"Ingestão concluída. Nós inseridos/atualizados: {nodes_pushed}, Arestas: {edges_pushed}")

    def raw_query(self, query_str: str) -> str:
        """Raw graph query returning formatted sub-graph text."""
        logger.debug(f"Querying graph com texto base: {query_str}")
        
        try:
            graph_path = self.out_dir / "graph.json"
            if not graph_path.exists():
                return "Erro: Grafo não encontrado para realizar a consulta (graph.json inexistente)."
                
            question = f"Elabore uma dissertação sobre: {query_str}. IMPORTANTE: preserve rigorosamente as referências (arquivos, seções e páginas)."
            
            logger.debug(f"Executando graphify query: {question}")
            
            result = subprocess.run([
                sys.executable, "-m", "graphify", "query", question,
                "--graph", str(graph_path), "--backend", "ollama", "--model", "qwen2.5:7b-instruct"
            ], capture_output=True, text=True, check=True)
            
            if result.stdout:
                return f"Dissertação extraída do Grafo de Conhecimento (Graphify):\n{result.stdout.strip()}"
            else:
                return "Nenhuma informação relevante retornada pelo Grafo."
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar graphify query: {e.stderr}")
            return "Erro ao acessar o Grafo via graphify query."
        except Exception as e:
            logger.error(f"Erro inesperado no graphify query: {e}")
            return "Erro inesperado ao acessar o Grafo."

    def get_retriever(self) -> BaseRetriever:
        return CustomGraphRetriever(self)

class CustomGraphRetriever(BaseRetriever):
    """LlamaIndex native BaseRetriever wrapper for Graphify Kuzu store."""
    def __init__(self, graph_store: GraphifyKuzuStore):
        self.graph_store = graph_store
        super().__init__()
        
    def _retrieve(self, query_bundle, **kwargs) -> List[NodeWithScore]:
        res_text = self.graph_store.raw_query(query_bundle.query_str)
        node = TextNode(text=res_text, metadata={"source": "graphify_kuzu"})
        return [NodeWithScore(node=node, score=1.0)]
