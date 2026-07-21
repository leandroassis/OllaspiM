import sys
from pathlib import Path

from src.cli.parser import get_config
from src.utils.logger import logger
from src.ingestion.docling_parser import DoclingParser
from src.ingestion.markitdown_parser import MarkItDownParser
from src.ingestion.code_parser import CodeParser
from src.ingestion.code_enricher import CodeEnricher
from src.storage.graphify_store import GraphifyKuzuStore
from src.storage.chroma_store import ChromaStore
from src.worker.orchestrator import WorkerOrchestrator
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.generator import ReportGenerator
from src.llm.ollama_client import OllamaClient

def main():
    logger.info("Iniciando LaspiLM...")
    
    try:
        config = get_config()
        logger.info(f"Paths validados: docs={config['docs']}, code={config['code']}, past={config['past']}, tests={config['tests']}")
        
        # Etapa 2: Inicializando componentes
        logger.info("Inicializando LLMs e Bancos de Dados...")
        try:
            llm_coder = OllamaClient(model="qwen2.5-coder:7b-instruct")
            llm_gen = OllamaClient(model="qwen2.5:7b-instruct")
            enricher = CodeEnricher(llm_coder)
            graph_store = GraphifyKuzuStore()
            vector_store = ChromaStore()
        except Exception as e:
            logger.error(f"Falha ao conectar com dependências externas (Ollama, Kuzu, Chroma): {e}")
            sys.exit(1)
        
        # Ingestão Docs
        logger.info("Processando Documentação...")
        try:
            docling_parser = DoclingParser()
            markitdown_parser = MarkItDownParser()
            code_parser = CodeParser()
            
            # Documentos
            for doc_file in config["docs"].rglob("*"):
                if doc_file.is_file():
                    if doc_file.suffix.lower() == ".pdf":
                        res = docling_parser.parse(doc_file)
                        graph_store.add_document(str(doc_file), res["content"], {"type": "document"})
                    elif doc_file.suffix.lower() in [".xlsx", ".docx", ".csv"]:
                        res = markitdown_parser.parse(doc_file)
                        graph_store.add_document(str(doc_file), res["content"], {"type": "table_office"})
            
            # Código Fonte
            logger.info("Processando Código Fonte e enriquecendo com LLM...")
            for code_file in config["code"].rglob("*"):
                if code_file.is_file():
                    res = code_parser.parse(code_file)
                    for func in res.get("functions", []):
                        enriched = enricher.enrich_function(str(code_file), func)
                        graph_store.add_document(
                            f"{code_file.name}:{enriched.nome_funcao}", 
                            enriched.model_dump_json(), 
                            {"type": "code_function"}
                        )
            # Build Graphify Graph
            logger.info("Executando extração do Graphify (Build Graph)...")
            graph_store.build_graph()
            
            # Relatórios Legados (Past)
            logger.info("Processando Relatórios Legados para VectorRAG...")
            legacy_docs = []
            for past_file in config["past"].rglob("*.pdf"):
                if past_file.is_file():
                    res = docling_parser.parse(past_file)
                    legacy_docs.append({
                        "id": str(past_file),
                        "content": res["content"],
                        "metadata": {"type": "legacy_report"}
                    })
            vector_store.add_documents(legacy_docs)
        except Exception as e:
            logger.warning(f"Parsers não puderam ser concluídos ou bibliotecas ausentes: {e}")

        # Etapa 3: Triagem
        logger.info("Etapa 3: Triagem de Ensaios")
        orchestrator = WorkerOrchestrator(ensaios_json_path="src/worker/ensaios.json")
        test_ids = orchestrator.get_test_list(config["tests"])
        valid_tests = orchestrator.filter_automatable_tests(test_ids)
        
        # Etapa 4: Geração de Parecer
        logger.info("Etapa 4: Geração de Pareceres (RAG Híbrido)")
        retriever = HybridRetriever(graph_store, vector_store)
        generator = ReportGenerator(retriever, llm_gen)
        
        for test in valid_tests:
            tid = test["id"]
            descricao = test.get("descricao", "Sem descrição")
            parecer = generator.generate_parecer(tid, descricao)
            
            logger.info(f"\n{'='*40}\nPARECER FINAL PARA: {tid}\n{parecer}\n{'='*40}")
            
    except Exception as e:
        logger.critical(f"Falha na execução do pipeline: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
