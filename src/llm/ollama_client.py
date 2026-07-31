import instructor
from openai import OpenAI
from typing import Type, TypeVar
import os
from pydantic import BaseModel
from src.utils.logger import logger
from src.utils.exceptions import StructuredOutputException

T = TypeVar('T', bound=BaseModel)

LLAMA_SERVER_DEFAULT_PORT = int(os.environ.get("LLAMA_SERVER_PORT", "8080"))
LLAMA_SERVER_DEFAULT_HOST = f"http://localhost:{LLAMA_SERVER_DEFAULT_PORT}/v1"

class LLMClient:
    """Client for llama.cpp server (OpenAI-compatible API) with structured output support via Instructor."""
    
    def __init__(self, host: str = None, model: str = "local-model"):
        """
        Args:
            host: URL base do servidor llama.cpp (ex: 'http://localhost:8080/v1').
                  Se None, lê de LLAMA_SERVER_PORT env var ou usa porta 8080.
            model: Nome do modelo passado ao servidor (o llama-server ignora este campo,
                   mas é obrigatório para a API OpenAI. Use qualquer string).
        """
        self.host = host or LLAMA_SERVER_DEFAULT_HOST
        self.model = model
        try:
            self.client = instructor.from_openai(
                OpenAI(
                    base_url=self.host,
                    api_key="llama-cpp",  # llama-server não valida a chave
                ),
                mode=instructor.Mode.JSON
            )
            self._raw_client = OpenAI(base_url=self.host, api_key="llama-cpp")
        except Exception as e:
            logger.error(f"Erro ao inicializar LLMClient: {e}")
            raise
            
    def generate_structured(self, prompt: str, response_model: Type[T]) -> T:
        """Generates a structured Pydantic model response via llama.cpp server."""
        try:
            logger.debug(f"Chamando llama-server modelo={self.model} host={self.host}")
            logger.debug(f"=== PROMPT (Structured) ===\n{prompt}\n===========================")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em análise de conformidade de segurança criptográfica. Responda em JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                response_model=response_model,
                max_retries=3,
            )
            
            logger.debug(f"=== RESPONSE (Structured) ===\n{response.model_dump_json(indent=2)}\n===========================")
            return response
        except Exception as e:
            logger.error(f"Falha ao gerar saída estruturada via llama-server: {e}")
            raise StructuredOutputException(f"LLM failed to produce valid JSON: {e}")

    def generate(self, prompt: str) -> str:
        """Generates a plain text response via llama.cpp server."""
        try:
            logger.debug(f"Chamando llama-server (plain text) modelo={self.model} host={self.host}")
            logger.debug(f"=== PROMPT (Plain) ===\n{prompt}\n======================")
            
            response = self._raw_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em análise de conformidade de segurança criptográfica."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content
            logger.debug(f"=== RESPONSE (Plain) ===\n{content}\n========================")
            return content
        except Exception as e:
            logger.error(f"Falha ao gerar texto plano via llama-server: {e}")
            raise RuntimeError(f"LLM failed to produce valid text: {e}")


# Alias de compatibilidade — mantém imports antigos funcionando durante a transição
OllamaClient = LLMClient
