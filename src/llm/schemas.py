from pydantic import BaseModel, Field
from typing import List

class CodeFunctionMetadata(BaseModel):
    nome_funcao: str = Field(description="Nome da função extraída.")
    arquivo: str = Field(description="Caminho ou nome do arquivo fonte.")
    linhas: str = Field(description="Intervalo de linhas (ex: 45-78).")
    resumo_linguagem_natural: str = Field(description="Resumo do que a função faz.")
    logica_de_negocio: List[str] = Field(description="Lista de passos que detalham a lógica de negócio.")
    condicoes_de_borda_e_limites: str = Field(description="Condições de borda, hardcodes e limites.")
    funcoes_chamadas: List[str] = Field(description="Lista de funções que são chamadas internamente.")
    codigo_fonte_bruto: str = Field(description="Código fonte exato da função.")
