# Limpa os bancos de dados e pastas de staging
clean:
	@echo "Limpando bancos de dados e artefatos gerados..."
	rm -rf ./kuzu_db
	rm -rf ./chroma_db
	rm -rf .graphify_input
	rm -rf .vector_only_input
	rm -f .ingestion_manifest.json
	rm -rf graphify-out
	rm -rf graphify-docs
	rm -rf graphify-code
	rm -rf .pytest_cache
	@echo "Limpeza concluída!"

# Roda todos os testes
test:
	@echo "Executando os testes..."
	.venv/bin/pytest -v tests/

# Roda a conversão 
# --skip-code-llm
convert *args:
	@echo "Iniciando etapa de conversão..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --convert {{args}}

graphify-extract:
	@echo "Executando extração do graphify em subpastas..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify extract .graphify_input/docs --out graphify-docs --backend openai --max-concurrency 1 --token-budget 2048
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify extract .graphify_input/code --out graphify-code --backend openai --max-concurrency 1 --token-budget 2048
	@echo "Mesclando os grafos..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify merge-graphs graphify-docs/graphify-out/graph.json graphify-code/graphify-out/graph.json --out .
	@echo "Gerando clusters..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify cluster-only . --backend openai
	@echo "Exportando HTML..."
	.venv/bin/python -m graphify export html .

# Roda a ingestão vetorial no ChromaDB
ingestion *args:
	@echo "Iniciando etapa de indexação vetorial..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --ingestion {{args}}

# Roda o RAG
# --no-past 
run *args:
	@echo "Iniciando orquestração RAG híbrido..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --run {{args}}

# Executa todo o pipeline sequencialmente
all: clean convert graphify-extract ingestion run

# Roda a conversão para os dados de teste
test-convert *args:
	@echo "Iniciando etapa de conversão (TEST)..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --convert {{args}}

# Roda a ingestão vetorial no ChromaDB para os dados de teste
test-ingest *args:
	@echo "Iniciando etapa de indexação vetorial (TEST)..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --ingestion --token-budget 500 {{args}}

# Roda o RAG para os dados de teste
test-run *args:
	@echo "Iniciando orquestração RAG híbrido (TEST)..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --run {{args}}
