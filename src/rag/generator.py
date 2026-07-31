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
        
    def generate_parecer(self, test_id: str, test_description: str, no_past: bool = False, num_chunks: int = 20) -> str:
        """Generates the consolidated response in 2 steps."""
        logger.info(f"Gerando Parecer para o ensaio {test_id} (Fases 5a e 5b, num_chunks={num_chunks})")
        
        # Fases 2 a 4
        projeto_ctx, legado_ctx = self.retriever.retrieve_context(test_id, test_description, no_past, num_chunks=num_chunks)
        
        # FASE 5a: Análise Técnica Pura (Projeto)
        prompt_5a = f"""
Você é um auditor de validação de sistemas embarcados.
Sua missão é redigir um ÚNICO texto dissertativo coeso avaliando se o equipamento atende ao Objetivo do Ensaio. 
Para isso, você deve utilizar o [Contexto Semântico] para entendimento e raciocínio técnico.
Obrigatóriamente, você deve utilizar trechos exatos da [Evidência Bruta para Citação] ao mencionar limites numéricos, nomes de variáveis ou funções.

ID do Ensaio: {test_id}
Objetivo: {test_description}

=== DADOS DO PROJETO (Restritos via Grafo e Limitados a {num_chunks} Chunks) ===
{projeto_ctx}

Redija sua análise técnica no formato de uma dissertação única e fluida. CITE explicitamente o nome de cada arquivo (usando a tag [Arquivo Origem: X]) ao longo do seu texto para fundamentar suas conclusões técnicas com base na evidência bruta. Não divida a resposta em tópicos soltos.
"""
        logger.info(f"[{test_id}] Executando Fase 5a (Análise Técnica Pura)...")
        try:
            res_5a = self.llm.generate_structured(prompt_5a, AnalisePreliminar)
            analise_rascunho = res_5a.analise_tecnica
            logger.debug(f"[{test_id}] Rascunho da Fase 5a gerado com sucesso.")
        except Exception as e:
            logger.error(f"[{test_id}] Erro na Fase 5a: {e}")
            analise_rascunho = "Não foi possível extrair a lógica técnica do projeto."

        if no_past:
            logger.info(f"[{test_id}] Flag --no-past ativa. Pulando Fase 5b e retornando apenas Análise Técnica Pura.")
            return f"Status: Indefinido (Requer validação humana)\n\nParecer:\n{analise_rascunho}"

        # FASE 5b: Adequação de Tom e Formato (Relatórios Legados)
        prompt_5b = f"""
Você é um redator sênior de pareceres de conformidade criptográfica.
Abaixo você possui a "Análise Técnica" bruta que resolve a conformidade do equipamento.
Sua missão é reescrevê-la no FORMATO FINAL, espelhando o tom de voz, estilo de texto, jargões e nível de formalidade dos Pareceres Históricos Antigos.

ID do Ensaio: {test_id}

=== ANÁLISE TÉCNICA (Única Fonte da Verdade) ===
{analise_rascunho}

=== PARECERES HISTÓRICOS (Modelos de Escrita) ===
{legado_ctx}

Redija o parecer final adequando a análise para este padrão institucional.
REGRA ABSOLUTA: O conteúdo técnico, as decisões de conformidade e as citações (tags [Arquivo Origem: X]) devem vir OBRIGATORIAMENTE da "Análise Técnica". 
Os pareceres históricos fornecidos servem APENAS como gabarito de estilo de escrita e formatação (utilize o [Contexto Semântico] deles para apreender o estilo). Sob nenhuma hipótese adicione informações técnicas dos relatórios legados na sua resposta final nem crie referências a eles.
"""
        logger.info(f"[{test_id}] Executando Fase 5b (Adequação aos Padrões Históricos)...")
        try:
            result = self.llm.generate_structured(prompt_5b, ParecerOutput)
            return f"Status: {result.status}\n\nParecer:\n{result.parecer_tecnico}"
        except Exception as e:
            logger.error(f"[{test_id}] Erro ao gerar parecer final (Fase 5b): {e}")
            return "Erro ao gerar o parecer final."
