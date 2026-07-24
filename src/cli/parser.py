import argparse
from pathlib import Path
from typing import Dict
import sys
from src.utils.exceptions import PathNotFoundException
from src.utils.logger import logger

def parse_args(args=None) -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="LaspiLM - AI Test Analyzer (GraphRAG + Vector RAG)")
    
    parser.add_argument("--docs", type=str, required=True, help="Caminho do diretório de documentação.")
    parser.add_argument("--code", type=str, required=True, help="Caminho do diretório do código-fonte.")
    parser.add_argument("--past", type=str, required=True, help="Caminho do diretório de relatórios legados.")
    parser.add_argument("--tests", type=str, required=True, help="Caminho do arquivo .txt contendo a lista de ensaios a executar.")
    
    parser.add_argument("--convert", action="store_true", help="Executa a etapa de conversão de documentos e extração de código (Gera os .md).")
    parser.add_argument("--ingestion", action="store_true", help="Executa a ingestão dos dados convertidos no ChromaDB.")
    parser.add_argument("--run", action="store_true", help="Executa a filtragem topológica e o RAG para os testes definidos.")
    parser.add_argument("--skip-code-llm", action="store_true", help="Pula a etapa de geração de documentação de código via LLM.")
    parser.add_argument("--token-budget", type=int, default=512, help="Tamanho máximo (em tokens) dos chunks originais durante a ingestão (default: 512).")
    parser.add_argument("--no-past", action="store_true", help="Desabilita o envio de chunks de relatórios anteriores para o modelo na fase run.")
    
    return parser.parse_args(args)

def validate_paths(args: argparse.Namespace) -> Dict[str, Path]:
    """Validates if the provided paths exist."""
    paths = {
        "docs": Path(args.docs),
        "code": Path(args.code),
        "past": Path(args.past),
        "tests": Path(args.tests)
    }
    
    for name, path in paths.items():
        if not path.exists():
            logger.error(f"O caminho para '--{name}' não foi encontrado: {path}")
            raise PathNotFoundException(f"Path not found: {path}")
            
    if not paths["tests"].is_file():
        logger.error(f"O caminho para '--tests' deve ser um arquivo: {paths['tests']}")
        raise PathNotFoundException(f"Tests path must be a file: {paths['tests']}")
        
    return paths

def get_config(args=None) -> Dict[str, Path]:
    """Parses and validates arguments, returning valid paths."""
    try:
        parsed_args = parse_args(args)
        return validate_paths(parsed_args)
    except PathNotFoundException:
        sys.exit(1)
