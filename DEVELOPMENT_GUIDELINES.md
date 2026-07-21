# Diretrizes de Desenvolvimento: LaspiLM

Este documento estabelece os padrões de código, princípios de arquitetura, práticas de teste e diretrizes que qualquer desenvolvedor ou agente de IA deve seguir estritamente ao implementar o repositório **LaspiLM**.

---

## 1. Padrões Gerais do Código

1. **Linguagem:** Python 3.10+
2. **Tipagem Estática:** Todas as funções, métodos e classes **devem** utilizar *Type Hints* completos (`typing`, `pydantic`).
3. **Formatação e Estilo:** Seguir **PEP 8**. Recomenda-se uso de `ruff` ou `black` para linting/formatação.
4. **Interface CLI:** A entrada principal da aplicação deve usar `argparse` para ler as flags obrigatórias:
   - `--docs`: Caminho do diretório de documentação.
   - `--code`: Caminho do diretório do código-fonte.
   - `--past`: Caminho do diretório de relatórios legados.
   - `--tests`: Caminho do arquivo `.txt` contendo a lista de ensaios a executar.

---

## 2. Princípios SOLID e Arquitetura

O código deve seguir rigorosamente os princípios **SOLID**:

### 2.1. Single Responsibility Principle (SRP)
Cada classe ou módulo deve ter apenas **uma** responsabilidade no pipeline.

### 2.2. Open/Closed Principle (OCP)
* Crie interfaces abstratas (`BaseParser`, `BaseVectorStore`, `BaseGraphStore`) para permitir a adição de novos parsers de arquivos ou bancos de dados sem alterar a lógica principal da aplicação.

### 2.3. Liskov Substitution Principle (LSP)
* Qualquer implementação de `BaseParser` (ex: `PDFParser`, `OfficeParser`) deve ser perfeitamente substituível no fluxo de ingestão sem quebrar o orquestrador.

### 2.4. Interface Segregation Principle (ISP)
* Não forçar classes a dependerem de interfaces que não utilizam. Separar explicitamente a interface do Banco de Grafos (`GraphStoreInterface`) da interface do Banco Vetorial (`VectorStoreInterface`).

### 2.5. Dependency Inversion Principle (DIP)
* O orquestrador (`LlamaIndex` / `WorkerExecutor`) deve depender de **abstrações** de bancagem de dados e inferência, injetadas via **Injeção de Dependência** (Dependency Injection).

---

## 3. Gestão de Modelos com Ollama

1. **Launcher Local:** O **Ollama** deve ser utilizado como servidor/launcher local das LLMs.
2. **Eficiência de VRAM / RAM:**
   - As chamadas ao Ollama devem explicitar parâmetros de alocação (ex: `keep_alive`, `num_gpu`) para garantir que os modelos operem prioritariamente em RAM quando a GPU atingir o limite de VRAM.
   - Os modelos utilizados por padrão devem ser `qwen2.5-coder:7b-instruct` (ou versão equivalente quantizada em Q4_K_M / Q8_0).
3. **Structured Outputs:**
   - A comunicação com a CodeLLM **deve utilizar Pydantic** combinando `ollama` / `instructor` para garantir retornos em JSON rigorosamente válidos.

---

## 4. Logging e Rastreabilidade

1. **Biblioteca Padrão:** Utilizar estritamente a biblioteca nativa `logging` do Python.
2. **Configuração de Logs:**
   - Criar um módulo `logger.py` centralizado.
   - O log deve ter dois handlers: **Console (StreamHandler)** com formatação colorida/amigável e **Arquivo (FileHandler)** em `logs/app.log` com timestamp ISO.
3. **Níveis de Log:**
   - `INFO`: Início e fim de cada etapa do pipeline (ex: "Iniciando conversão de PDFs com Docling", "Ensaio EN.III.1.2.04-01 finalizado").
   - `DEBUG`: Detalhes de chunks extraídos, consultas executadas no KùzuDB/ChromaDB e tempo de resposta de prompts.
   - `WARNING`: Ignorando arquivos não suportados, ensaios marcados como `automatizavel: "Não"`.
   - `ERROR` / `CRITICAL`: Falhas ao carregar arquivos, respostas malformatadas da LLM ou erros nos caminhos do sistema.

---

## 5. Estratégia de Testes

O projeto **deve contar com cobertura completa de testes automatizados** utilizando `pytest`.

### 5.1. Estrutura de Pastas de Testes
Os casos de teste e arquivos sintéticos de validação devem estar salvos obrigatoriamente na seguinte estrutura:

```text
tests/
├── conftest.py            # Fixtures globais do pytest
├── docs/                  # PDFs, DOCX e XLSX fictícios de teste
├── code/                  # Arquivos .cpp / .py fictícios de teste
├── past/                  # Relatórios legados de teste
├── test.txt               # Lista de índices de ensaios para execução do teste
├── unit/                  # Testes unitários por componente
│   ├── test_parsers.py
│   ├── test_ast.py
│   ├── test_codellm.py
│   └── test_worker.py
└── integration/           # Testes de integração do pipeline completo
    └── test_pipeline.py
```

### 5.2. Regras de Escrita de Testes
1. **Isolamento via Mocks:** Testes unitários **não devem dependente de chamadas reais ao Ollama ou de VRAM**. Use `unittest.mock` ou `pytest-mock` para simular as respostas da LLM.
2. **Testes de Ingestão:** Verificar se o `Docling` e o `MarkItDown` geram saídas `.md` válidas a partir dos arquivos presentes em `tests/docs` e `tests/past`.
3. **Testes de Código:** Garantir que o Tree-sitter extraia funções corretamente a partir de amostras em `tests/code`.
4. **Testes de Triagem:** Garantir que o `Worker` leia corretamente o `tests/test.txt` e filtre ensaios conforme o `ensaios.json`.
5. **Testes End-to-End (E2E):** Teste de integração rodando o pipeline completo com dados mínimos contidos no diretório `tests/`.

---

## 6. Tratamento de Exceções

1. **Exceções Customizadas:** Criar exceções de domínio em `exceptions.py`:
   - `PathNotFoundException`: Erros ao abrir diretórios de entrada.
   - `ParsingException`: Erros do Docling ou MarkItDown.
   - `StructuredOutputException`: Quando a LLM falha em respeitar o Pydantic Schema após retentativas.
2. **Graceful Failures:** Se um único arquivo em `--docs` ou uma função em `--code` falhar, o pipeline deve registrar o erro no `logging` e continuar o processamento dos demais arquivos sem interromper toda a execução.