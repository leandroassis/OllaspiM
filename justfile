# Limpa os bancos de dados e pastas de staging
clean:
	@echo "Limpando bancos de dados e artefatos gerados..."
	rm -rf ./kuzu_db
	rm -rf ./chroma_db
	rm -rf .graphify_input
	rm -rf graphify-out
	@echo "Limpeza concluída!"

# Roda todos os testes
test:
	@echo "Executando os testes..."
	.venv/bin/pytest -v tests/

# Roda o pipeline apontando para a pasta data/
run:
	@echo "Iniciando pipeline do LaspiLM..."
	.venv/bin/python main.py --code data/code --past data/past --docs data/docs --tests data/tests.txt
