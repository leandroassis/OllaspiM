from typing import Dict, Any
from src.rag.hybrid_retriever import HybridRetriever
from src.llm.ollama_client import OllamaClient
from src.utils.logger import logger
from pydantic import BaseModel, Field

class AnalisePreliminar(BaseModel):
    analise: str = Field(description="Análise técnica preliminar baseada exclusivamente no Grafo de Conhecimento (regras, parâmetros, códigos).")

class ParecerOutput(BaseModel):
    status: str = Field(description="'Conforme' ou 'Não Conforme'")
    parecer_tecnico: str = Field(description="O texto detalhado do parecer.")

class ReportGenerator:
    """Generates the final test report (Parecer) using a 2-Phase RAG approach."""
    
    def __init__(self, retriever: HybridRetriever, llm_client: OllamaClient = None):
        self.retriever = retriever
        self.llm = llm_client or OllamaClient(model="qwen2.5-coder:7b-instruct")
        
    def generate_parecer(self, test_id: str, test_description: str) -> str:
        """Generates the consolidated response using Phase 1 and Phase 2."""
        logger.info(f"Gerando Parecer para o ensaio {test_id} em 2 Fases")
        
        # Recupera ambos os contextos
        graph_ctx, vector_ctx = self.retriever.retrieve_context(test_description)
        
        # FASE 1: Navegação no Grafo e Resposta Preliminar
        prompt_fase_1 = f"""
Você é um especialista em validação de equipamentos e sistemas embarcados.
Sua tarefa na FASE 1 é gerar uma análise preliminar fundamentada EXCLUSIVAMENTE na documentação, parâmetros e códigos do equipamento.

ID do Ensaio: {test_id}
Descrição: {test_description}

=== CONTEXTO DO PROJETO (Grafo de Conhecimento) ===
{graph_ctx}

Elabore a análise preliminar considerando as cláusulas do PDF, tabelas e funções associadas, justificando tecnicamente os limites do projeto.
"""
        logger.info(f"[{test_id}] Executando Fase 1 (Análise Preliminar via Grafo)...")
        try:
            res_fase1 = self.llm.generate_structured(prompt_fase_1, AnalisePreliminar)
            analise_preliminar = res_fase1.analise
            logger.info(f"[{test_id}] Análise Preliminar Fase 1:\n{analise_preliminar}")
        except Exception as e:
            logger.error(f"[{test_id}] Erro na Fase 1: {e}")
            analise_preliminar = "Falha ao gerar análise preliminar baseada no Grafo."
            
        # FASE 2: Injeção de Histórico e Retroalimentação
        prompt_fase_2 = f"""
Você é um especialista em validação de equipamentos e sistemas embarcados.
Sua tarefa na FASE 2 é redigir o PARECER TÉCNICO FORMAL consolidado.

Você já realizou uma análise técnica preliminar do projeto. Agora, você deve alinhar essa análise com os pareceres históricos passados da organização para garantir consistência e jurisprudência nos julgamentos.

ID do Ensaio: {test_id}
Descrição: {test_description}

=== SUA ANÁLISE PRELIMINAR (Baseada no Projeto Atual) ===
{analise_preliminar}

=== HISTÓRICO DE RELATÓRIOS SIMILARES (Vector RAG) ===
{vector_ctx}

Com base nesses dados consolidados, redija o parecer final justificando a conformidade ou não conformidade do equipamento.
Mantenha o tom de voz técnico e padronizado de acordo com o histórico.

IMPORTANTE: Você DEVE obrigatoriamente referenciar o nome do arquivo (e a seção/página, se disponível) de onde extraiu cada informação, tanto para os componentes/dados do projeto atual quanto para os pareceres históricos.
"""
        logger.info(f"[{test_id}] Executando Fase 2 (Injeção de Histórico e Parecer Final)...")
        try:
            result = self.llm.generate_structured(prompt_fase_2, ParecerOutput)
            return f"Status: {result.status}\n\nParecer:\n{result.parecer_tecnico}"
        except Exception as e:
            logger.error(f"[{test_id}] Erro ao gerar parecer final na Fase 2: {e}")
            return "Erro ao gerar o parecer."
