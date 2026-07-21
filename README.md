# LaspiLM

LaspiLM - AI Test Analyzer (GraphRAG + Vector RAG)

## Pré-requisitos

Para rodar o projeto, você precisará do **Python 3.10+** (recomendado 3.12) e do **Ollama** rodando localmente com os seguintes modelos de linguagem:

- `qwen2.5:7b-instruct`
- `qwen2.5-coder:7b-instruct`

Para baixar os modelos no Ollama, basta executar no terminal:
```bash
ollama pull qwen2.5:7b-instruct
ollama pull qwen2.5-coder:7b-instruct
```

## Instalação e Configuração

É altamente recomendado o uso de um ambiente virtual (`venv`) para instalar as dependências do projeto isoladamente.

1. **Criar o ambiente virtual na raiz do projeto:**
   ```bash
   python3 -m venv .venv
   ```

2. **Ativar o ambiente virtual:**
   - No **Linux/macOS**:
     ```bash
     source .venv/bin/activate
     ```
   - No **Windows**:
     ```bash
     .venv\Scripts\activate
     ```

3. **Instalar as bibliotecas (dependências):**
   Com o ambiente ativado (você verá o prefixo `(.venv)` no terminal), instale as bibliotecas contidas no `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

## Executando o Programa

O ponto de entrada da aplicação é o script `main.py`. Ele utiliza argumentos de linha de comando para referenciar os diretórios e arquivos necessários para a triagem e execução da RAG (Geração Aumentada de Recuperação).

### Argumentos Obrigatórios

- `--docs`: Diretório que contém a documentação técnica (PDFs, planilhas, Word, etc.).
- `--code`: Diretório do código-fonte do módulo ou sistema a ser analisado.
- `--past`: Diretório que contém relatórios legados ou passados para busca vetorial.
- `--tests`: Caminho para o arquivo `.txt` contendo os IDs dos ensaios a serem avaliados.

### Exemplo Prático de Uso

Com o ambiente ativado e o Ollama em execução, rode o seguinte comando:
```bash
python main.py \
    --docs tests/docs \
    --code tests/code \
    --past tests/past \
    --tests tests/tests.txt
```

## Executando os Testes Automatizados

O projeto utiliza a biblioteca `pytest` para rodar os testes das etapas do pipeline de forma automatizada (parsers, integrações, etc.).

Para executar todos os testes da aplicação, certifique-se de que o `.venv` está ativado e rode:
```bash
pytest
```

Se desejar visualizar o log de saída de forma detalhada, você pode usar os parâmetros extras `-v` (verbose) e `-s` (não capturar logs do stdout):
```bash
pytest -v -s
```
