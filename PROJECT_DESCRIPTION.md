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
1. O `TreeSitter` lê cada arquivo de código (`.c`, `.cpp`, etc.), identifica o intervalo exato de linhas de cada função e **extrai o nome nativo da função navegando pela árvore sintática (AST)**.
2. Cada bloco de função fatiado é enviado para a `CodeLLM` utilizando `Pydantic` com suporte a *Structured Output* para gerar um descritivo semântico em JSON.
3. Esse JSON é transmutado em um artefato `.md` (ex: `code_desc_kryptus.c_lines_30-40.md`) e associado logicamente à coleção global de `documentation`, unificando manuais e código no mesmo ecossistema vetorial.

#### 2.1. Análise da Documentação Técnica
* **Arquivos PDF (`.pdf`):** Convertidos via **Docling** para `.md`, preservando a estrutura de tabelas e a numeração das páginas.
* **Arquivos do Office/Tabelas (`.docx`, `.xlsx`, `.csv`, `.doc`, `.xls`):** Convertidos via **MarkItDown** para `.md`.
* **Arquivos Descartados:** Imagens e binários sem suporte são sumariamente ignorados.

#### 2.2. Análise dos Relatórios Históricos Legados
* PDFs na pasta `--past` são processados pelo **Docling** para extração de Markdown.
* **Limpeza de Preâmbulo:** Uma expressão regular agressiva varre o output gerado e poda absolutamente todo o conteúdo (índices, metodologias vazias) que antecede a primeira ocorrência da palavra `"Parecer:"`, focando estritamente na essência da resposta do auditor.

#### 2.3. Estruturação dos Bancos de Dados
* **Grafo de Conhecimento (`Graphify`):** Recebe os Markdowns da documentação (inclusive as descrições de código), faz a extração de entidades semânticas, relaciona os nós e roda um algoritmo de "Detecção de Comunidades" (Clusterização). O output relacional é salvo no `graph.json`.
* **Banco Vetorial (`ChromaDB`):**
  * Aplica um `SentenceSplitter` agressivo de 512 tokens para **todas** as coleções (Documentação e Legados).
  * **Política Tolerância Zero (No-Noise Policy):** Para a coleção `legacy_reports`, qualquer chunk gerado (mesmo fatiado em 512 tokens) que não contiver literalmente a substring `"parecer:"` é impedido de ser gravado no banco, eliminando o risco de alucinações de estilo.

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

### Etapa 4: Arquitetura de Recuperação Vector ➔ Graph ➔ Vector

A etapa de colheita de contexto e geração do parecer agora emprega uma abordagem Híbrida State of the Art:

1. **Fase 2a (Multi-Query Entity Extraction):** A LLM extrai do texto do ensaio uma lista pontual de requisitos técnicos.
2. **Fase 2b (Busca Semântica Semente):** O ChromaDB realiza consultas independentes (`top_k=2`) para CADA entidade extraída, recuperando os arquivos primários do projeto que respondem a essas entidades e formando os "Arquivos Semente".
3. **Fase 3 (Expansão Topológica):** O algoritmo viaja até o Grafo de Conhecimento (NetworkX) buscando os nós referentes aos Arquivos Semente e expande a rede puxando:
   - Vizinhos diretos (Distância = 1).
   - Todos os arquivos que pertencem à **mesma "Community"** (Cluster detectado no Graphify).
4. **Fase 4 (Busca Semântica Refinada):** O algoritmo volta ao ChromaDB e executa uma super-busca (`top_k=7`) **restringindo matematicamente** a pesquisa apenas aos arquivos resgatados na "teia" do grafo, blindando o retriever contra alucinações e arquivos irrelevantes. Paralelamente, uma busca isolada levanta a jurisprudência nos relatórios legados baseando-se no objetivo do ensaio.

### Etapa 5: Síntese de Parecer em 2 Fases

1. **Fase 5a (Análise Técnica Pura):** A LLM Qwen recebe exclusivamente os chunks do projeto (Código + Manuais) e é orientada a redigir um rascunho determinístico sobre a conformidade técnica do teste. Ela é obrigada a inserir `[Arquivo Origem: X]` apontando os trechos exatos de manuais ou códigos que provam suas alegações.
2. **Fase 5b (Adequação Histórica):** A LLM avalia a Análise Técnica (Fase 5a) crua contra os chunks filtrados dos relatórios legados e **reescreve** a análise imitando o jargão, nível de formalidade e padrão de resposta da instituição. Regras cruciais aplicadas:
   - A LLM é terminantemente proibida de citar os arquivos legados como justificativa.
   - Os arquivos de origem do projeto mapeados na Fase 5a são religiosamente mantidos no texto final.

---

## 5. Orçamento de Recursos e Hardware

Devido às limitações do sistema em que vamos executar esse projeto, os modelos LLM e a extração de dados de entrada não poderão ser paralelizados. Deverá existir algum worker que organiza uma fila para que cada etapa seja realizada de forma sequencial.

| Recurso | Capacidade Disponível | Alocação no Pipeline |
| :--- | :--- | :--- |
| **RAM do Sistema** | 32 GB | - Processamento do `Docling` / `MarkItDown` (~4 GB)<br>- Execução do `KùzuDB` e `ChromaDB` (~6 GB)<br>- Orquestração Python e buffers (~4 GB) |
| **VRAM da GPU** | 12 GB | - **Fase Ingestão:** `Qwen2.5-Coder-7B` quantizado Q5/Q8 (~6.5 GB VRAM)<br>- **Fase Inferência:** `Qwen2.5-Coder-7B` / `Llama-3.1-8B` (~7 GB VRAM) |
