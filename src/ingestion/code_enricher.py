from pathlib import Path
from typing import Dict, Any, List
from src.llm.ollama_client import OllamaClient
from src.utils.logger import logger

class CodeEnricher:
    """Combines code parsing output with LLM to generate structured markdown documentation."""
    
    def __init__(self, llm_client: OllamaClient = None):
        self.llm = llm_client or OllamaClient()
        
    def enrich_function(self, source_file: str, function_data: Dict[str, Any]) -> str:
        """Takes raw function data and enriches it via LLM returning Markdown."""
        code_bruto = function_data.get("codigo_fonte_bruto", "")
        linhas = function_data.get("lines", "")
        nome_funcao = function_data.get("name", "UnknownFunction")
        
        prompt = (
            f"Analise a seguinte função '{nome_funcao}' extraída do arquivo '{source_file}' "
            f"(linhas {linhas}):\n\n"
            f"```\n{code_bruto}\n```\n\n"
            "Crie um relatório em formato Markdown com as seguintes seções:\n"
            "- **Resumo em Linguagem Natural**: O que a função faz.\n"
            "- **Lógica de Negócio**: Lista de passos detalhando a lógica.\n"
            "- **Condições de Borda e Limites**: Hardcodes, limites e tratamentos de exceção.\n"
            "- **Funções Chamadas**: Lista de funções chamadas internamente.\n\n"
            "Retorne APENAS o Markdown."
        )
        
        md_content = self.llm.generate(prompt)
        
        # Prepend the file and function info
        header = f"# Função: {nome_funcao}\n**Arquivo**: {source_file}\n**Linhas**: {linhas}\n\n"
        
        return header + md_content
