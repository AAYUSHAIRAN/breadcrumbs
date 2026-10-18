.PHONY: db api web test lint

db:     ## start FalkorDB (graph + cache) — browser UI at http://localhost:3002
	docker compose up -d

api:    ## backend on http://localhost:8000 (docs at /docs)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:    ## frontend on http://localhost:3000
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && cd ../frontend && npm run lint
