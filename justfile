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
# Uso: just convert            (usa MobiusDevelopment/Bonsai-27B-Q1_0-gguf)
#      just convert meu-modelo:7b
#      just convert meu-modelo:7b --skip-code-llm
convert model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" *args:
	@echo "Iniciando etapa de conversão (modelo: {{model}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --convert --model {{model}} {{args}}

graphify-extract model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf":
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
# Uso: just ingestion            (usa MobiusDevelopment/Bonsai-27B-Q1_0-gguf)
#      just ingestion meu-modelo:7b
#      just ingestion meu-modelo:7b --no-past
ingestion model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" *args:
	@echo "Iniciando etapa de indexação vetorial (modelo: {{model}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --ingestion --model {{model}} {{args}}

# Roda o RAG
# Uso: just run                          (modelo e chunks default)
#      just run meu-modelo:7b            (modelo custom)
#      just run meu-modelo:7b 30         (modelo custom + 30 chunks)
#      just run meu-modelo:7b 30 --no-past
run model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" num_chunks="20" *args:
	@echo "Iniciando orquestração RAG híbrido (modelo: {{model}}, chunks: {{num_chunks}})..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt --run --model {{model}} --num-chunks {{num_chunks}} {{args}}

# Executa todo o pipeline sequencialmente
# Uso: just all                           (tudo com defaults)
#      just all meu-modelo:7b            (modelo custom)
#      just all meu-modelo:7b 30         (modelo custom + 30 chunks no run)
all model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" num_chunks="20":
	just convert {{model}} --skip-code-llm
	just graphify-extract {{model}}
	just ingestion {{model}} --no-past
	just run {{model}} {{num_chunks}} --no-past

# Roda a conversão para os dados de teste
test-convert model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" *args:
	@echo "Iniciando etapa de conversão (TEST, modelo: {{model}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --convert --model {{model}} {{args}}

# Roda a ingestão vetorial no ChromaDB para os dados de teste
test-ingest model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" *args:
	@echo "Iniciando etapa de indexação vetorial (TEST, modelo: {{model}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --ingestion --token-budget 500 --model {{model}} {{args}}

# Roda o RAG para os dados de teste
test-run model="MobiusDevelopment/Bonsai-27B-Q1_0-gguf" num_chunks="20" *args:
	@echo "Iniciando orquestração RAG híbrido (TEST, modelo: {{model}}, chunks: {{num_chunks}})..."
	.venv/bin/python main.py --code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt --run --model {{model}} --num-chunks {{num_chunks}} {{args}}
