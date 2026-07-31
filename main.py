import sys
import shutil
import json
from pathlib import Path
import pypdfium2 as pdfium
from tqdm import tqdm

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

MAX_FILE_SIZE = 20 * 1024 * 1024

def preprocess_file(file_path: Path) -> Path:
    """Verifica tamanho e trunca PDFs maiores que 700 paginas. Retorna novo Path ou None."""
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            logger.warning(f"Arquivo ignorado por exceder 20MB: {file_path}")
            return None
    except Exception as e:
        logger.warning(f"Erro ao verificar tamanho de {file_path}: {e}")
        return None
        
    if file_path.suffix.lower() == ".pdf":
        try:
            pdf = pdfium.PdfDocument(file_path)
            if len(pdf) > 700:
                logger.warning(f"PDF com mais de 700 paginas, truncando: {file_path}")
                new_pdf = pdfium.PdfDocument.new()
                new_pdf.import_pages(pdf, list(range(700)))
                
                truncated_path = file_path.with_name(f"{file_path.stem}_truncated.pdf")
                new_pdf.save(str(truncated_path))
                new_pdf.close()
                pdf.close()
                
                file_path.unlink() # exclui o original
                return truncated_path
            else:
                pdf.close()
        except Exception as e:
            logger.warning(f"Erro ao processar PDF com pypdfium2: {file_path}. Detalhes: {e}")
            
    return file_path

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
        manifest_path = Path(".ingestion_manifest.json")
        convert_cache_path = Path(".convert_cache.json")
        ingest_cache_path = Path(".ingest_cache.json")
        
        if args.convert:
            logger.info("=== ETAPA: CONVERSÃO ===")
            graphify_input_docs = graphify_input_dir / "docs"
            graphify_input_code = graphify_input_dir / "code"
            graphify_input_past = graphify_input_dir / "past"
            graphify_input_docs.mkdir(parents=True, exist_ok=True)
            graphify_input_code.mkdir(parents=True, exist_ok=True)
            graphify_input_past.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Inicializando CodeLLM e parsers... (modelo: {args.model})")
            llm_coder = OllamaClient(model=args.model)
            enricher = CodeEnricher(llm_coder)
            docling_parser = DoclingParser()
            markitdown_parser = MarkItDownParser()
            code_parser = CodeParser()
            
            # Dictionary to act as a manifest for the ingestion step
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            else:
                manifest = []
                
            if convert_cache_path.exists():
                with open(convert_cache_path, "r", encoding="utf-8") as f:
                    convert_cache = set(json.load(f))
            else:
                convert_cache = set()

            def save_convert_state(file_id: str):
                convert_cache.add(file_id)
                with open(convert_cache_path, "w", encoding="utf-8") as f:
                    json.dump(list(convert_cache), f, indent=4)
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)
            
            # 1. Process Docs
            logger.info("Processando Documentação...")
            docs_files = list(config["docs"].rglob("*"))
            for doc_file in tqdm(docs_files, desc="Docs"):
                if doc_file.is_file():
                    file_id = str(doc_file.resolve())
                    if file_id in convert_cache:
                        logger.info(f"Skipping cached document: {doc_file.name}")
                        continue
                        
                    processed_file = preprocess_file(doc_file)
                    if not processed_file:
                        continue
                        
                    content = ""
                    if processed_file.suffix.lower() == ".pdf":
                        res = docling_parser.parse(processed_file)
                        content = res["content"]
                    elif processed_file.suffix.lower() in [".xlsx", ".docx", ".csv"]:
                        res = markitdown_parser.parse(processed_file)
                        content = res["content"]
                    
                    if content:
                        safe_name = f"doc_{processed_file.name}.md"
                        out_path = graphify_input_docs / safe_name
                        out_path.write_text(content, encoding="utf-8")
                        manifest.append({"file": str(out_path), "source_file": safe_name, "collection": "documentation", "doc_type": "normative"})
                    save_convert_state(file_id)

            # 2. Process Past Reports (EXCLUDED FROM GRAPHIFY)
            if not getattr(args, 'no_past', False):
                logger.info("Processando Relatórios Legados (Apenas Vetorial)...")
                past_files = list(config["past"].rglob("*.pdf"))
                for past_file in tqdm(past_files, desc="Legados"):
                    if past_file.is_file():
                        file_id = str(past_file.resolve())
                        if file_id in convert_cache:
                            logger.info(f"Skipping cached past report: {past_file.name}")
                            continue
                            
                        processed_file = preprocess_file(past_file)
                        if not processed_file:
                            continue
                            
                        res = docling_parser.parse(processed_file)
                        safe_name = f"past_{processed_file.name}.md"
                        out_path = graphify_input_past / safe_name
                        out_path.write_text(res["content"], encoding="utf-8")
                        manifest.append({"file": str(out_path), "source_file": processed_file.name, "collection": "legacy_reports", "doc_type": "legacy"})
                        save_convert_state(file_id)
            else:
                logger.info("Flag --no-past ativa. Pulando processamento de relatórios legados.")

            # 3. Process Code
            logger.info("Processando Código Fonte e copiando originais...")
            code_files = list(config["code"].rglob("*"))
            for code_file in tqdm(code_files, desc="Code"):
                if code_file.is_file():
                    file_id = str(code_file.resolve())
                    if file_id in convert_cache:
                        logger.info(f"Skipping cached code file: {code_file.name}")
                        continue
                        
                    processed_file = preprocess_file(code_file)
                    if not processed_file:
                        continue
                        
                    # Copy raw file to .graphify_input/code
                    shutil.copy2(processed_file, graphify_input_code / processed_file.name)
                    
                    # Parse and enrich code
                    if not getattr(args, 'skip_code_llm', False):
                        try:
                            res = code_parser.parse(processed_file)
                            for func in res.get("functions", []):
                                md_content = enricher.enrich_function(str(processed_file.name), func)
                                safe_name = f"code_desc_{processed_file.name}_lines_{func.get('lines', 'unknown')}.md"
                                out_path = graphify_input_code / safe_name
                                out_path.write_text(md_content, encoding="utf-8")
                                manifest.append({
                                    "file": str(out_path), 
                                    "source_file": safe_name, 
                                    "collection": "documentation", 
                                    "doc_type": "code_desc", 
                                    "raw_code": func.get("codigo_fonte_bruto", "")
                                })
                        except Exception as e:
                            logger.warning(f"Erro ao fazer parse do código {processed_file}: {e}")
                    save_convert_state(file_id)

            logger.info("Conversão concluída. Arquivos gerados em subpastas de .graphify_input/")

        elif args.ingestion:
            logger.info("=== ETAPA: INGESTÃO VETORIAL ===")
            if not manifest_path.exists():
                logger.error("Manifesto de ingestão não encontrado. Rode --convert primeiro.")
                sys.exit(1)
                
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                
            if ingest_cache_path.exists():
                with open(ingest_cache_path, "r", encoding="utf-8") as f:
                    ingest_cache = set(json.load(f))
            else:
                ingest_cache = set()
                
            # Initialize ChromaStore (this will handle separate collections)
            store = ChromaStore(token_budget=args.token_budget, model=args.model)
            
            for item in tqdm(manifest, desc="Ingestão"):
                file_path = Path(item["file"])
                file_id = str(file_path.resolve())
                
                if file_id in ingest_cache:
                    logger.info(f"Skipping already ingested file: {file_path.name}")
                    continue
                    
                if file_path.exists():
                    logger.info(f"Ingerindo vetores para: {file_path.name}")
                    content = file_path.read_text(encoding="utf-8")
                    payload = [{
                        "id": file_path.name,
                        "content": content,
                        "metadata": {
                            "source_file": item["source_file"],
                            "type": item["collection"],
                            "doc_type": item.get("doc_type", "normative"),
                            "raw_code": item.get("raw_code", "")
                        },
                        "collection": item["collection"]
                    }]
                    
                    store.add_documents(payload)
                    ingest_cache.add(file_id)
                    with open(ingest_cache_path, "w", encoding="utf-8") as f:
                        json.dump(list(ingest_cache), f, indent=4)
                        
            logger.info("Ingestão vetorial concluída com sucesso.")

        elif args.run:
            logger.info("=== ETAPA: ORQUESTRAÇÃO RAG (RUN) ===")
            
            logger.info(f"Inicializando modelos e orquestrador... (modelo: {args.model})")
            llm_gen = OllamaClient(model=args.model)
            orchestrator = WorkerOrchestrator(ensaios_json_path="src/worker/ensaios.json")
            test_ids = orchestrator.get_test_list(config["tests"])
            valid_tests = orchestrator.filter_automatable_tests(test_ids)
            
            store = ChromaStore(model=args.model)
            # HybridRetriever now takes ChromaStore and the path to graph.json
            retriever = HybridRetriever(graph_json_path="graphify-out/graph.json", vector_store=store, llm_client=llm_gen)
            generator = ReportGenerator(retriever, llm_gen)
            
            for test in tqdm(valid_tests, desc="RUN Pareceres"):
                tid = test["id"]
                descricao = test.get("descricao", "Sem descrição")
                parecer = generator.generate_parecer(tid, descricao, no_past=getattr(args, 'no_past', False))
                
                logger.info(f"\n{'='*40}\nPARECER FINAL PARA: {tid}\n{parecer}\n{'='*40}")
                
        else:
            logger.error("Nenhuma ação especificada. Use --convert, --ingestion ou --run.")
            sys.exit(1)
            
    except Exception as e:
        logger.critical(f"Falha na execução do pipeline: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
