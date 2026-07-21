from pathlib import Path
from typing import Dict, Any, List
from src.llm.ollama_client import OllamaClient
from src.llm.schemas import CodeFunctionMetadata
from src.utils.logger import logger

class CodeEnricher:
    """Combines code parsing output with LLM to generate structured metadata."""
    
    def __init__(self, llm_client: OllamaClient = None):
        self.llm = llm_client or OllamaClient()
        
    def enrich_function(self, source_file: str, function_data: Dict[str, Any]) -> CodeFunctionMetadata:
        """Takes raw function data and enriches it via LLM."""
        code_bruto = function_data.get("codigo_fonte_bruto", "")
        linhas = function_data.get("lines", "")
        
        prompt = (
            f"Analise a seguinte função extraída do arquivo {source_file} "
            f"(linhas {linhas}):\n\n"
            f"```\n{code_bruto}\n```\n\n"
            "Preencha todos os campos do JSON conforme solicitado."
        )
        
        metadata = self.llm.generate_structured(prompt, CodeFunctionMetadata)
        
        # Override to ensure integrity with original parsing
        metadata.arquivo = source_file
        metadata.linhas = linhas
        metadata.codigo_fonte_bruto = code_bruto
        
        return metadata
