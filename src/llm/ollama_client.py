import instructor
from openai import OpenAI
from typing import Type, TypeVar
from pydantic import BaseModel
from src.utils.logger import logger
from src.utils.exceptions import StructuredOutputException

T = TypeVar('T', bound=BaseModel)

class OllamaClient:
    """Wrapper for Ollama to generate structured outputs using Instructor."""
    
    def __init__(self, host: str = "http://localhost:11434/v1", model: str = "qwen2.5-coder:7b-instruct"):
        self.host = host
        self.model = model
        try:
            self.client = instructor.from_openai(
                OpenAI(
                    base_url=self.host,
                    api_key="ollama"
                ),
                mode=instructor.Mode.JSON
            )
        except Exception as e:
            logger.error(f"Erro ao inicializar Ollama Client: {e}")
            raise
            
    def generate_structured(self, prompt: str, response_model: Type[T]) -> T:
        """Generates a structured Pydantic model response."""
        try:
            logger.debug(f"Chamando Ollama modelo={self.model}")
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
            logger.error(f"Falha ao gerar saída estruturada no Ollama: {e}")
            raise StructuredOutputException(f"LLM failed to produce valid JSON: {e}")

    def generate(self, prompt: str) -> str:
        """Generates a plain text response."""
        try:
            logger.debug(f"Chamando Ollama (plain text) modelo={self.model}")
            logger.debug(f"=== PROMPT (Plain) ===\n{prompt}\n======================")
            
            # Use raw OpenAI client directly to avoid instructor expecting a JSON response
            raw_client = OpenAI(base_url=self.host, api_key="ollama")
            
            response = raw_client.chat.completions.create(
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
            logger.error(f"Falha ao gerar texto plano no Ollama: {e}")
            raise RuntimeError(f"LLM failed to produce valid text: {e}")
