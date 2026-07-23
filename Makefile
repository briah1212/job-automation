.PHONY: help setup start stop restart logs clean test migrate

help:
	@echo "Job Application Automation Platform - Available Commands:"
	@echo "  make setup       - Full setup + start (generates .env, builds, starts everything)"
	@echo "  make start       - Start all services (build if needed)"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-api    - View API logs"
	@echo "  make logs-web    - View frontend logs"
	@echo "  make logs-worker - View browser-worker logs"
	@echo "  make migrate     - Run database migrations"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make shell-api   - Shell into API container"
	@echo "  make shell-db    - PostgreSQL shell"

setup:
	./setup-portable.sh

start:
	docker compose up -d --build
	@echo "Services starting..."
	@echo "Web:        http://localhost:$$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 3002)"
	@echo "API:        http://localhost:$$(grep -E '^API_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 8001)"
	@echo "API Docs:   http://localhost:$$(grep -E '^API_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 8001)/docs"
	@echo "Mock ATS:   http://localhost:$$(grep -E '^MOCK_ATS_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 8080)"

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-web:
	docker compose logs -f web

logs-worker:
	docker compose logs -f browser-worker

migrate:
	docker compose exec api alembic upgrade head

test:
	docker compose exec api pytest tests/ -v
	docker compose exec browser-worker pytest tests/ -v
	cd apps/web && npm test

clean:
	docker compose down -v
	rm -rf storage/screenshots/*
	rm -rf storage/resumes/*
	@echo "Cleaned containers, volumes, and storage"

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-job_automation}
