# Limpa os bancos de dados e pastas de staging
clean:
	@echo "Limpando bancos de dados e artefatos gerados..."
	rm -rf ./kuzu_db
	rm -rf ./chroma_db
	rm -rf .graphify_input
	rm -rf .vector_only_input
	rm -f .ingestion_manifest.json
	rm -rf graphify-out
	rm -rf .pytest_cache
	@echo "Limpeza concluída!"

# Roda todos os testes
test:
	@echo "Executando os testes..."
	.venv/bin/pytest -v tests/

# Roda a conversão
convert:
	@echo "Iniciando etapa de conversão..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --convert

# Roda a extração do graphify externamente
graphify-extract:
	@echo "Executando extração do graphify..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify extract .graphify_input --out . --backend openai --max-concurrency 1 --token-budget 2048
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL=llama3.1:8b .venv/bin/python -m graphify cluster-only . --backend openai
	.venv/bin/python -m graphify export html .

# Roda a ingestão vetorial no ChromaDB
ingestion:
	@echo "Iniciando etapa de indexação vetorial..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --ingestion

# Roda o RAG
run:
	@echo "Iniciando orquestração RAG híbrido..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --run

# Executa todo o pipeline sequencialmente
all: clean convert graphify-extract ingestion run
