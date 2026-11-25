.PHONY: db up down install dev test

db:        ## start only Postgres
	docker compose up -d db

up:        ## start Postgres + backend in Docker
	docker compose up --build

down:
	docker compose down

install:   ## install backend for local dev
	cd backend && pip install -e ".[dev]"

dev:       ## run backend locally with auto-reload (needs `make db` + .env)
	cd backend && uvicorn app.main:app --reload --env-file ../.env

test:      ## run tests (no API key or database needed)
	cd backend && DATABASE_URL= pytest -q
