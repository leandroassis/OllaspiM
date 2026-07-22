from typing import Dict, Any
from src.rag.hybrid_retriever import HybridRetriever
from src.llm.ollama_client import OllamaClient
from src.utils.logger import logger
from pydantic import BaseModel, Field

class AnalisePreliminar(BaseModel):
    analise_tecnica: str = Field(description="Análise técnica baseada exclusivamente no código e documentação recuperados do projeto, citando os arquivos de origem.")
    
class ParecerOutput(BaseModel):
    status: str = Field(description="'Conforme' ou 'Não Conforme'")
    parecer_tecnico: str = Field(description="O texto detalhado do parecer adequadamente redigido seguindo os jargões e padrões históricos.")

class ReportGenerator:
    """Generates the final test report (Parecer) using a 2-Step Synthesis (Phase 5)."""
    
    def __init__(self, retriever: HybridRetriever, llm_client: OllamaClient = None):
        self.retriever = retriever
        self.llm = llm_client or OllamaClient(model="qwen2.5-coder:7b-instruct")
        
    def generate_parecer(self, test_id: str, test_description: str) -> str:
        """Generates the consolidated response in 2 steps."""
        logger.info(f"Gerando Parecer para o ensaio {test_id} (Fases 5a e 5b)")
        
        # Fases 2 a 4
        projeto_ctx, legado_ctx = self.retriever.retrieve_context(test_id, test_description)
        
        # FASE 5a: Análise Técnica Pura (Projeto)
        prompt_5a = f"""
Você é um auditor de validação de sistemas embarcados.
Responda tecnicamente ao objetivo do Ensaio baseando-se EXCLUSIVAMENTE nos trechos de código e manuais recuperados do sistema abaixo.

ID do Ensaio: {test_id}
Objetivo: {test_description}

=== DADOS DO PROJETO (Restritos via Grafo) ===
{projeto_ctx}

Redija uma avaliação técnica detalhada. CITE explicitamente o nome de cada arquivo (usando a tag [Arquivo Origem: X]) que baseou sua conclusão.
"""
        logger.info(f"[{test_id}] Executando Fase 5a (Análise Técnica Pura)...")
        try:
            res_5a = self.llm.generate_structured(prompt_5a, AnalisePreliminar)
            analise_rascunho = res_5a.analise_tecnica
            logger.debug(f"[{test_id}] Rascunho da Fase 5a gerado com sucesso.")
        except Exception as e:
            logger.error(f"[{test_id}] Erro na Fase 5a: {e}")
            analise_rascunho = "Não foi possível extrair a lógica técnica do projeto."

        # FASE 5b: Adequação de Tom e Formato (Relatórios Legados)
        prompt_5b = f"""
Você é um redator sênior de pareceres de conformidade criptográfica.
Abaixo você possui a "Análise Técnica" bruta que resolve a conformidade do equipamento.
Sua missão é reescrevê-la no FORMATO FINAL, espelhando o tom de voz, estilo de texto, jargões e nível de formalidade dos Pareceres Históricos Antigos.

ID do Ensaio: {test_id}

=== ANÁLISE TÉCNICA (Base da Conclusão) ===
{analise_rascunho}

=== PARECERES HISTÓRICOS (MOLDES / PADRÕES PARA IMITAR) ===
{legado_ctx}

Redija o parecer final adequando a análise para este padrão institucional.
MANTENHA RIGOROSAMENTE todas as citações técnicas e tags [Arquivo Origem: X] provenientes da "Análise Técnica".
NUNCA cite os relatórios legados como fonte de conclusão ou crie novas tags de origem baseadas neles. O relatório legado serve APENAS como modelo de estilo e jargão.
"""
        logger.info(f"[{test_id}] Executando Fase 5b (Adequação aos Padrões Históricos)...")
        try:
            result = self.llm.generate_structured(prompt_5b, ParecerOutput)
            return f"Status: {result.status}\n\nParecer:\n{result.parecer_tecnico}"
        except Exception as e:
            logger.error(f"[{test_id}] Erro ao gerar parecer final (Fase 5b): {e}")
            return "Erro ao gerar o parecer final."
