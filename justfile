# Limpa os bancos de dados e pastas de staging
clean:
	@echo "Limpando bancos de dados e artefatos gerados..."
	rm -rf ./kuzu_db
	rm -rf ./chroma_db
	rm -rf .graphify_input
	rm -f .ingestion_manifest.json
	rm -f .convert_cache.json
	rm -f .ingest_cache.json
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
# Flags extras opcionais: --skip-code-llm
# Uso: just convert            (usa bonsai:8b)
#      just convert meu-modelo:7b
#      just convert meu-modelo:7b --skip-code-llm
convert model="bonsai:8b" *args:
	@echo "Iniciando etapa de conversão (modelo: {{model}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --convert --model {{model}} {{args}}

graphify-extract model="bonsai:8b":
	@echo "Executando extração do graphify em subpastas (modelo: {{model}})..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL={{model}} .venv/bin/python -m graphify extract .graphify_input/docs --out graphify-docs --backend openai --max-concurrency 2 --token-budget 2048
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL={{model}} .venv/bin/python -m graphify extract .graphify_input/code --out graphify-code --backend openai --max-concurrency 2 --token-budget 2048
	@echo "Mesclando os grafos..."
	mkdir -p graphify-out
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL={{model}} .venv/bin/python -m graphify merge-graphs graphify-docs/graphify-out/graph.json graphify-code/graphify-out/graph.json --out graphify-out/graph.json
	@echo "Gerando clusters..."
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama OPENAI_MODEL={{model}} .venv/bin/python -m graphify cluster-only . --backend openai
	@echo "Exportando HTML..."
	.venv/bin/python -m graphify export html .

# Roda a ingestão vetorial no ChromaDB
# Uso: just ingestion            (usa bonsai:8b)
#      just ingestion meu-modelo:7b
#      just ingestion meu-modelo:7b --no-past
ingestion model="bonsai:8b" *args:
	@echo "Iniciando etapa de indexação vetorial (modelo: {{model}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --ingestion --model {{model}} {{args}}

# Roda o RAG
# Uso: just run            (usa bonsai:8b)
#      just run meu-modelo:7b
#      just run meu-modelo:7b --no-past
run model="bonsai:8b" *args:
	@echo "Iniciando orquestração RAG híbrido (modelo: {{model}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --run --model {{model}} {{args}}

# Executa todo o pipeline sequencialmente
# Uso: just all            (usa bonsai:8b)
#      just all meu-modelo:7b
all model="bonsai:8b":
	just convert {{model}} --skip-code-llm	
	just graphify-extract {{model}}
	just ingestion {{model}} --no-past
	just run {{model}} --no-past

# Roda a conversão para os dados de teste
test-convert model="bonsai:8b" *args:
	@echo "Iniciando etapa de conversão (TEST, modelo: {{model}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --convert --model {{model}} {{args}}

# Roda a ingestão vetorial no ChromaDB para os dados de teste
test-ingest model="bonsai:8b" *args:
	@echo "Iniciando etapa de indexação vetorial (TEST, modelo: {{model}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --ingestion --token-budget 500 --model {{model}} {{args}}

# Roda o RAG para os dados de teste
test-run model="bonsai:8b" *args:
	@echo "Iniciando orquestração RAG híbrido (TEST, modelo: {{model}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --run --model {{model}} {{args}}
