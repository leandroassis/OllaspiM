# Especificação do Projeto: LaspiLM (GraphRAG + Vector RAG)

## 1. Visão Geral do Projeto

O **LaspiLM** é um sistema avançado de automação de análises de ensaios técnicos para validação de equipamentos (hardware, software embarcado e documentação associada). O sistema combina duas técnicas complementares de Recuperação Aumentada por Geração (**RAG**):

1. **GraphRAG (Grafo de Conhecimento):** Utilizado para mapear deterministicamente as relações entre especificações técnicas em PDF, parâmetros em planilhas/Word e a implementação real das funções no código-fonte em C/C++/Python/Java.
2. **Vector RAG (Busca Vetorial por Similaridade):** Utilizado para consultar a base histórica de relatórios legados e recuperar pareceres passados, garantindo consistência técnica, tom de voz padronizado e jurisprudência nos julgamentos.

---

## 2. Diagrama de Arquitetura

```
                                        [DOCUMENTAÇÃO]
                                        /    |    \
                                        /     |     \
                            [CÓDIGO-FONTE]  [PDFS]  [TABELAS E DOCS]
                                |           |            |
                            (TreeSitter)  (Docling)   (MarkItDown)
                                |           |            |
                            [CodeLLM]       |            |
                                \           |            /
                                ▼          ▼           ▼
                                [    GRAPHIFY    ]
                                            |
                                            v
 [JSON / LISTA ENSAIOS] ──> [WORKER] ──> [LlamaIndex] <─── [ChromaDB] <── (Docling) <── [RELATÓRIOS LEGADO]
                                              |
                                           (Prompt)
                                              v
                                           [QWEN]
                                              |
                                              v
                                          [PARECER]
```

---

## 3. Pilha de Tecnologias (Tech Stack)

| Componente | Tecnologia | Função e Descrição |
| :--- | :--- | :--- |
| **Parsing Sintático de Código** | `Tree-Sitter` | Analisador estático (AST parser) que realiza o fatiamento determinístico de funções, métodos e estruturas de código sem depender de LLMs. |
| **Enriquecimento de Código** | `CodeLLM` (`Qwen2.5-Coder-7B`) | Modelo de linguagem especializado em código que analisa cada bloco extraído pelo Tree-Sitter e gera metadados estruturados em JSON via `Pydantic` + `Ollama`/`Instructor`. |
| **Parsing de PDFs Técnicos** | `Docling` (IBM) | Extrator de alta fidelidade visual e estrutural para PDFs, preservando tabelas técnicas, hierarquia de seções e paginação. |
| **Parsing de Office/Tabelas** | `MarkItDown` (Microsoft) | Conversor de baixa latência para arquivos `.docx`, `.xlsx`, `.csv`, `.doc` e `.xls` em Markdown limpo. |
| **Estruturação de Grafo** | `Graphify` + `KùzuDB` | Ferramenta de mapeamento de conhecimento que unifica os outputs em Markdown e os JSONs de código em um banco de grafos local em disco. |
| **Armazenamento Vetorial** | `ChromaDB` | Banco de dados vetorial leve e embarcado em Python para indexação e busca por similaridade dos relatórios legados. |
| **Triagem & Orquestração CLI** | `Worker` (Python Script) | Script de controle de fluxo que valida argumentos CLI (`--docs`, `--code`, `--past`, `--tests`), lê a lista de ensaios e consulta o `ensaios.json`. |
| **Orquestrador RAG** | `LlamaIndex` | Framework de RAG híbrido que consulta o `Graphify` (KùzuDB) e o `ChromaDB`, formata o contexto e constrói o prompt para a LLM principal. |
| **LLM Principal** | `Qwen` (`Qwen2.5-14B` quantizado) | Modelo responsável pela síntese do contexto, raciocínio lógico-técnico e redação final do Parecer de Ensaio. |

---

## 4. Fluxo Detalhado do Pipeline

### Etapa 1: Injeção e Ingestão de Dados
O pipeline é disparado via linha de comando informando os caminhos de entrada:

```bash
python main.py --docs ./caminho/documentacao               --code ./caminho/codigo_fonte               --past ./caminho/relatorios_legados               --tests ./ensaios_alvo.txt
```

1. **Varredura Recursiva:** O sistema abre recursivamente os diretórios `--docs`, `--code` e `--past`.
2. **Validação de Paths:** Verifica a existência dos caminhos e encerra graciosamente em caso de erro.
3. **Segregação de Tipos:** Arquivos são estritamente categorizados entre **Código-Fonte**, **Documentos Técnicos** e **Relatórios Legados**.

---

### Etapa 2: Processamento e Estruturação de Dados

#### 2.0. Análise de Código-Fonte (`TreeSitter` + `CodeLLM`)
1. O `TreeSitter` lê cada arquivo de código (`.c`, `.cpp`, `.h`, `.hpp`, `.py`, etc.) e identifica o intervalo exato de linhas de cada função.
2. Cada bloco de função fatiado é enviado para a `CodeLLM` utilizando `Pydantic` com suporte a *Structured Output*:

```json
{
  "nome_funcao": "check_mancal_temp",
  "arquivo": "src/drivers/mancal.cpp",
  "linhas": "45-78",
  "resumo_linguagem_natural": "Verifica se a temperatura do mancal ultrapassa o limite máximo e aciona o alarme de emergência.",
  "logica_de_negocio": [
    "Lê o valor do registrador analógico TEMP_REG_01",
    "Compara com o threshold codificado em rígido (90.0 C)",
    "Se exceder, altera o bit de status da flag ERR_OVERHEAT_02 para HIGH"
  ],
  "condicoes_de_borda_e_limites": "Define o limite fixo em 90.0. Não possui tratamento para sensor desconectado (retorno NaN).",
  "funcoes_chamadas": ["read_register", "set_alarm_flag"],
  "codigo_fonte_bruto": "bool check_mancal_temp(...) { ... }"
}
```

#### 2.1. Análise da Documentação Técnica
* **Arquivos PDF (`.pdf`):** Convertidos via **Docling** para `.md`, preservando a estrutura de tabelas e a numeração das páginas (enriquecidos com marcadores de rastreabilidade - documento, seção, página).
* **Arquivos do Office/Tabelas (`.docx`, `.xlsx`, `.csv`, `.doc`, `.xls`):** Convertidos via **MarkItDown** para `.md`.
* **Arquivos Descartados:** Arquivos de imagens e extensões de código-fonte são ignorados na pasta `--docs` para evitar duplicação.

#### 2.2. Análise dos Relatórios Históricos Legados
* PDFs na pasta `--past` são processados pelo **Docling** para extração de Markdown enriquecido com marcadores de rastreabilidade (`documento`, `seção`, `página`).

#### 2.3. Estruturação dos Bancos de Dados
* **Grafo de Conhecimento (`Graphify + KuzuDB` ):** Recebe os Markdowns da documentação e os JSONs enriquecidos da `CodeLLM`, estabelecendo arestas entre conceitos técnicos, limites de projeto e rotinas de código.
* **Banco Vetorial (`ChromaDB`):** Armazena os *chunks* vetorizados dos relatórios legados que mais se relacionam com a pergunta.
* **Isolamento de Bancos:** O Grafo de Conhecimento e o Banco Vetorial permanecem em instâncias/armazenamentos independentes.

---

### Etapa 3: Triagem de Ensaios (`Worker`)

1. O script lê o arquivo informado em `--tests` (`.txt`), onde cada linha corresponde a um código identificador de ensaio (ex: `EN.III.1.2.04-01`).
2. Para cada identificador, o `Worker` realiza um lookup no arquivo `ensaios.json`:

```json
{
  "EN.III.1.1.01-08": {
    "descricao": "Verificar lista de componentes, hardware, software, e delimitação da fronteira criptográfica.",
    "tipo_avaliacao": "Documental",
    "automatizavel": "Não",
    "justificativa": "Análise puramente documental de diagramas e listas de componentes."
  },
  "EN.III.1.2.04-01": {
    "descricao": "Verificar se a rotina de interrupção de sobretemperatura é acionada ao atingir o limite estipulado no manual.",
    "tipo_avaliacao": "Automatizada",
    "automatizavel": "Sim",
    "justificativa": "Validável via código C++ e especificações técnicas."
  }
}
```

3. **Lógica de Triagem:**
   * Se `"automatizavel": "Não"`, o ensaio é registrado como ignorado no relatório com a devida justificativa.
   * Se `"automatizavel": "Sim"`, o campo `"descricao"` é extraído e enviado como a consulta base ao **LlamaIndex**.

---

### Etapa 4: Construção do Parecer (RAG Híbrido em Duas Fases)

1. **Fase 1 (Navegação no Grafo):**
   * O **LlamaIndex** executa uma busca híbrida no **Graphify** (KùzuDB) utilizando a descrição do ensaio.
   * Recupera o subgrafo com as cláusulas do PDF, parâmetros em tabelas e as funções de código associadas.
   * A LLM principal (**Qwen**) gera uma resposta preliminar fundamentada exclusivamente na documentação do equipamento.

2. **Fase 2 (Injeção de Histórico e Retroalimentação):**
   * O **LlamaIndex** realiza uma consulta vetorial no **ChromaDB** procurando relatórios antigos referentes ao mesmo ensaio ou a falhas similares.
   * O **Qwen** recebe um prompt consolidado contendo:
     - A análise obtida via Grafo de Conhecimento.
     - Os *chunks* dos pareceres históricos passados.
   * A LLM redige o **PARECER** final consolidado, alinhando a exatidão técnica do projeto com os padrões históricos da organização.

---

## 5. Orçamento de Recursos e Hardware

Devido às limitações do sistema em que vamos executar esse projeto, os modelos LLM e a extração de dados de entrada não poderão ser paralelizados. Deverá existir algum worker que organiza uma fila para que cada etapa seja realizada de forma sequencial.

| Recurso | Capacidade Disponível | Alocação no Pipeline |
| :--- | :--- | :--- |
| **RAM do Sistema** | 32 GB | - Processamento do `Docling` / `MarkItDown` (~4 GB)<br>- Execução do `KùzuDB` e `ChromaDB` (~6 GB)<br>- Orquestração Python e buffers (~4 GB) |
| **VRAM da GPU** | 12 GB | - **Fase Ingestão:** `Qwen2.5-Coder-7B` quantizado Q5/Q8 (~6.5 GB VRAM)<br>- **Fase Inferência:** `Qwen2.5-Coder-7B` / `Llama-3.1-8B` (~7 GB VRAM) |
