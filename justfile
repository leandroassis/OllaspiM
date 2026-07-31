# ─── Configurações default ────────────────────────────────────────────────────
DEFAULT_PORT   := "9090"
DEFAULT_CHUNKS := "20"
MAX_CTX        := "8192"

# ─── Limpeza ──────────────────────────────────────────────────────────────────
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

# ─── Testes ───────────────────────────────────────────────────────────────────
test:
	@echo "Executando os testes..."
	.venv/bin/pytest -v tests/

# ─── llama.cpp server ─────────────────────────────────────────────────────────
# Sobe o servidor llama.cpp em background e salva o PID em .llama_server.pid
# Uso: just server-start path/to/model.gguf
#      just server-start path/to/model.gguf 9090        (porta custom)
#      just server-start path/to/model.gguf 9090 MAX_CTX   (porta + ctx size)
server-start model_path port=DEFAULT_PORT ctx=MAX_CTX:
	@echo "Iniciando llama-server (modelo: {{model_path}}, porta: {{port}}, ctx: {{ctx}})..."
	llama-server \
		--model {{model_path}} \
		--port {{port}} \
		--ctx-size {{ctx}} \
		--n-gpu-layers 99 \
		--parallel 2 \
		> .llama_server.log 2>&1 &
	echo $! > .llama_server.pid
	@echo "llama-server iniciado (PID: $(cat .llama_server.pid)). Log em .llama_server.log"
	@echo "Aguardando servidor ficar pronto..."
	sleep 8

# Para o servidor llama.cpp usando o PID salvo em .llama_server.pid
server-stop:
	@if [ -f .llama_server.pid ]; then \
		PID=$(cat .llama_server.pid); \
		echo "Parando llama-server (PID: $$PID)..."; \
		kill $$PID 2>/dev/null || true; \
		rm -f .llama_server.pid; \
		echo "llama-server parado."; \
	else \
		echo "Nenhum PID encontrado (.llama_server.pid não existe). Servidor já estava parado?"; \
	fi

# ─── Pipeline principal ───────────────────────────────────────────────────────

# Etapa de conversão — sobe o servidor, enriquece o código e derruba.
# model_path: caminho para o arquivo .gguf do modelo
# Uso: just convert path/to/model.gguf
#      just convert path/to/model.gguf 8080
#      just convert path/to/model.gguf 8080 --skip-code-llm
convert model_path port=DEFAULT_PORT *args:
	@echo "Iniciando etapa de conversão (modelo: {{model_path}}, porta: {{port}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code data/code --past data/past --docs data/docs --tests data/tests.txt \
		--convert --model {{model_path}} {{args}}
	just server-stop

# Extração do grafo — o servidor deve estar rodando (server-start).
# Uso: just graphify-extract path/to/model.gguf
#      just graphify-extract path/to/model.gguf 8080 --max-concurrency 2 --token-budget 8192
graphify-extract model_path port=DEFAULT_PORT ctx=MAX_CTX *args:
	@echo "Executando extração do graphify (modelo: {{model_path}}, porta: {{port}})..."
	GRAPHIFY_VIZ_NODE_LIMIT=25000 GRAPHIFY_OLLAMA_NUM_CTX=ctx \
		OPENAI_BASE_URL=http://localhost:{{port}}/v1 OPENAI_API_KEY=llama-cpp OPENAI_MODEL={{model_path}} \
		.venv/bin/python -m graphify extract .graphify_input/docs --out graphify-docs --backend openai {{args}}
	GRAPHIFY_VIZ_NODE_LIMIT=25000 GRAPHIFY_OLLAMA_NUM_CTX=ctx \
		OPENAI_BASE_URL=http://localhost:{{port}}/v1 OPENAI_API_KEY=llama-cpp OPENAI_MODEL={{model_path}} \
		.venv/bin/python -m graphify extract .graphify_input/code --out graphify-code --backend openai {{args}}
	@echo "Mesclando os grafos..."
	mkdir -p graphify-out
	GRAPHIFY_VIZ_NODE_LIMIT=25000 GRAPHIFY_OLLAMA_NUM_CTX=ctx \
		OPENAI_BASE_URL=http://localhost:{{port}}/v1 OPENAI_API_KEY=llama-cpp OPENAI_MODEL={{model_path}} \
		.venv/bin/python -m graphify merge-graphs graphify-docs/graphify-out/graph.json graphify-code/graphify-out/graph.json --out graphify-out/graph.json
	@echo "Gerando clusters..."
	GRAPHIFY_VIZ_NODE_LIMIT=25000 GRAPHIFY_OLLAMA_NUM_CTX=ctx \
		OPENAI_BASE_URL=http://localhost:{{port}}/v1 OPENAI_API_KEY=llama-cpp OPENAI_MODEL={{model_path}} \
		.venv/bin/python -m graphify cluster-only . --backend openai
	@echo "Exportando HTML..."
	GRAPHIFY_VIZ_NODE_LIMIT=25000 .venv/bin/python -m graphify export html .

# Ingestão vetorial — sobe o servidor, indexa e derruba.
# Uso: just ingestion path/to/model.gguf
#      just ingestion path/to/model.gguf 8080 --no-past
ingestion model_path port=DEFAULT_PORT *args:
	@echo "Iniciando etapa de indexação vetorial (modelo: {{model_path}}, porta: {{port}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code data/code --past data/past --docs data/docs --tests data/tests.txt \
		--ingestion --model {{model_path}} {{args}}
	just server-stop

# Etapa RAG — sobe o servidor, gera os pareceres e derruba.
# Uso: just run path/to/model.gguf
#      just run path/to/model.gguf 8080 20
#      just run path/to/model.gguf 8080 20 --no-past
run model_path port=DEFAULT_PORT num_chunks=DEFAULT_CHUNKS *args:
	@echo "Iniciando orquestração RAG híbrido (modelo: {{model_path}}, porta: {{port}}, chunks: {{num_chunks}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code data/code --past data/past --docs data/docs --tests data/tests.txt \
		--run --model {{model_path}} --num-chunks {{num_chunks}} {{args}}
	just server-stop

# ─── Pipeline completo ────────────────────────────────────────────────────────
# Sobe/derruba o servidor automaticamente em cada etapa.
# Uso: just all path/to/model.gguf
#      just all path/to/model.gguf 8080
#      just all path/to/model.gguf 8080 20
#      just all path/to/model.gguf 8080 20 MAX_CTX   (ctx size)
all model_path port=DEFAULT_PORT num_chunks=DEFAULT_CHUNKS ctx=MAX_CTX:
	just convert {{model_path}} {{port}} --skip-code-llm
	just server-start {{model_path}} {{port}} {{ctx}}
	just graphify-extract {{model_path}} {{port}} --max-concurrency 2 --token-budget MAX_CTX
	just server-stop
	just ingestion {{model_path}} {{port}} --no-past
	just run {{model_path}} {{port}} {{num_chunks}} --no-past

# ─── Receitas de teste ────────────────────────────────────────────────────────
test-convert model_path port=DEFAULT_PORT *args:
	@echo "Iniciando etapa de conversão (TEST, modelo: {{model_path}}, porta: {{port}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt \
		--convert --model {{model_path}} {{args}}
	just server-stop

test-ingest model_path port=DEFAULT_PORT *args:
	@echo "Iniciando etapa de indexação vetorial (TEST, modelo: {{model_path}}, porta: {{port}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt \
		--ingestion --token-budget 500 --model {{model_path}} {{args}}
	just server-stop

test-run model_path port=DEFAULT_PORT num_chunks=DEFAULT_CHUNKS *args:
	@echo "Iniciando orquestração RAG híbrido (TEST, modelo: {{model_path}}, porta: {{port}}, chunks: {{num_chunks}})..."
	just server-start {{model_path}} {{port}}
	LLAMA_SERVER_PORT={{port}} .venv/bin/python main.py \
		--code tests/code --past tests/past --docs tests/docs --tests tests/tests.txt \
		--run --model {{model_path}} --num-chunks {{num_chunks}} {{args}}
	just server-stop
