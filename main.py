import sys
import shutil
import json
from pathlib import Path

from src.cli.parser import get_config
from src.utils.logger import logger
from src.ingestion.docling_parser import DoclingParser
from src.ingestion.markitdown_parser import MarkItDownParser
from src.ingestion.code_parser import CodeParser
from src.ingestion.code_enricher import CodeEnricher
from src.storage.chroma_store import ChromaStore
from src.worker.orchestrator import WorkerOrchestrator
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.generator import ReportGenerator
from src.llm.ollama_client import OllamaClient

def main():
    logger.info("Iniciando LaspiLM...")
    
    try:
        config_args = get_config()
        # config_args includes 'docs', 'code', 'past', 'tests' (from parser validation)
        # However, get_config() returns a dictionary of paths. Wait, the original parser.py: 
        # def get_config(args=None) -> Dict[str, Path]: return validate_paths(parse_args(args))
        # But get_config doesn't return the raw args! Let me fix parser.py or just parse again here.
        import argparse
        from src.cli.parser import parse_args, validate_paths
        args = parse_args()
        config = validate_paths(args)
        
        graphify_input_dir = Path(".graphify_input")
        vector_only_dir = Path(".vector_only_input")
        manifest_path = Path(".ingestion_manifest.json")
        
        if args.convert:
            logger.info("=== ETAPA: CONVERSÃO ===")
            graphify_input_dir.mkdir(parents=True, exist_ok=True)
            vector_only_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info("Inicializando CodeLLM e parsers...")
            llm_coder = OllamaClient(model="qwen2.5-coder:7b-instruct")
            enricher = CodeEnricher(llm_coder)
            docling_parser = DoclingParser()
            markitdown_parser = MarkItDownParser()
            code_parser = CodeParser()
            
            # Dictionary to act as a manifest for the ingestion step
            manifest = []
            
            # 1. Process Docs
            logger.info("Processando Documentação...")
            for doc_file in config["docs"].rglob("*"):
                if doc_file.is_file():
                    content = ""
                    if doc_file.suffix.lower() == ".pdf":
                        res = docling_parser.parse(doc_file)
                        content = res["content"]
                    elif doc_file.suffix.lower() in [".xlsx", ".docx", ".csv"]:
                        res = markitdown_parser.parse(doc_file)
                        content = res["content"]
                    
                    if content:
                        safe_name = f"doc_{doc_file.name}.md"
                        out_path = graphify_input_dir / safe_name
                        out_path.write_text(content, encoding="utf-8")
                        manifest.append({"file": str(out_path), "source_file": safe_name, "collection": "documentation"})

            # 2. Process Past Reports (EXCLUDED FROM GRAPHIFY)
            logger.info("Processando Relatórios Legados (Apenas Vetorial)...")
            for past_file in config["past"].rglob("*.pdf"):
                if past_file.is_file():
                    res = docling_parser.parse(past_file)
                    safe_name = f"past_{past_file.name}.md"
                    out_path = vector_only_dir / safe_name
                    out_path.write_text(res["content"], encoding="utf-8")
                    manifest.append({"file": str(out_path), "source_file": past_file.name, "collection": "legacy_reports"})

            # 3. Process Code
            logger.info("Processando Código Fonte e copiando originais...")
            for code_file in config["code"].rglob("*"):
                if code_file.is_file():
                    # Copy raw file to .graphify_input
                    shutil.copy2(code_file, graphify_input_dir / code_file.name)
                    
                    # Parse and enrich code
                    try:
                        res = code_parser.parse(code_file)
                        for func in res.get("functions", []):
                            md_content = enricher.enrich_function(str(code_file.name), func)
                            safe_name = f"code_desc_{code_file.name}_lines_{func.get('lines', 'unknown')}.md"
                            out_path = graphify_input_dir / safe_name
                            out_path.write_text(md_content, encoding="utf-8")
                            manifest.append({"file": str(out_path), "source_file": safe_name, "collection": "documentation"})
                    except Exception as e:
                        logger.warning(f"Erro ao fazer parse do código {code_file}: {e}")

            # Save manifest in root to avoid graphify scanning it
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)
                
            logger.info("Conversão concluída. Arquivos gerados em .graphify_input/ e .vector_only_input/")

        elif args.ingestion:
            logger.info("=== ETAPA: INGESTÃO VETORIAL ===")
            if not manifest_path.exists():
                logger.error("Manifesto de ingestão não encontrado. Rode --convert primeiro.")
                sys.exit(1)
                
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                
            # Initialize ChromaStore (this will handle separate collections)
            store = ChromaStore()
            
            docs_payload = []
            for item in manifest:
                file_path = Path(item["file"])
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    docs_payload.append({
                        "id": file_path.name,
                        "content": content,
                        "metadata": {
                            "source_file": item["source_file"],
                            "type": item["collection"]
                        },
                        "collection": item["collection"]
                    })
                    
            store.add_documents(docs_payload)
            logger.info("Ingestão vetorial concluída com sucesso.")

        elif args.run:
            logger.info("=== ETAPA: ORQUESTRAÇÃO RAG (RUN) ===")
            
            logger.info("Inicializando modelos e orquestrador...")
            llm_gen = OllamaClient(model="qwen2.5:7b-instruct")
            orchestrator = WorkerOrchestrator(ensaios_json_path="src/worker/ensaios.json")
            test_ids = orchestrator.get_test_list(config["tests"])
            valid_tests = orchestrator.filter_automatable_tests(test_ids)
            
            store = ChromaStore()
            # HybridRetriever now takes ChromaStore and the path to graph.json
            retriever = HybridRetriever(graph_json_path="graphify-out/graph.json", vector_store=store, llm_client=llm_gen)
            generator = ReportGenerator(retriever, llm_gen)
            
            for test in valid_tests:
                tid = test["id"]
                descricao = test.get("descricao", "Sem descrição")
                parecer = generator.generate_parecer(tid, descricao)
                
                logger.info(f"\n{'='*40}\nPARECER FINAL PARA: {tid}\n{parecer}\n{'='*40}")
                
        else:
            logger.error("Nenhuma ação especificada. Use --convert, --ingestion ou --run.")
            sys.exit(1)
            
    except Exception as e:
        logger.critical(f"Falha na execução do pipeline: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
