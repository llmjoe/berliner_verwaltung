.PHONY: install dev db migrate crawl pipeline-vi test lint clean

install:
	uv pip install -e ".[all]"

dev: install db migrate

db:
	sudo docker compose up -d

migrate:
	alembic upgrade head

crawl:
	bv crawl-oparl

pipeline-vi: ## Run full pipeline for VI. Wahlperiode
	bv download-pdfs -t VI -n 3000
	bv extract-text -t VI -n 3000
	bv index-search -n 3000
	bv classify -t VI -n 3000

search: ## Start Streamlit search UI
	streamlit run app.py

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/ app.py
	mypy src/

stats:
	bv stats

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
