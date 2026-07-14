.PHONY: help setup start stop restart logs clean test migrate

help:
	@echo "Job Application Automation Platform - Available Commands:"
	@echo "  make setup       - Initial setup (install dependencies, create .env)"
	@echo "  make start       - Start all services"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-api    - View API logs"
	@echo "  make logs-web    - View frontend logs"
	@echo "  make migrate     - Run database migrations"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make shell-api   - Shell into API container"
	@echo "  make shell-db    - PostgreSQL shell"

setup:
	@echo "Setting up development environment..."
	cp backend/.env.example backend/.env || true
	cp apps/web/.env.example apps/web/.env.local || true
	@echo "Setup complete! Edit backend/.env and apps/web/.env.local if needed"
	@echo "Run 'make start' to start the application"

start:
	docker-compose up -d postgres redis minio api web mock-ats
	@echo "Services starting..."
	@echo "API:        http://localhost:8000"
	@echo "Web:        http://localhost:3000"
	@echo "Mock ATS:   http://localhost:8080"
	@echo "MinIO:      http://localhost:9001 (admin/admin)"
	@echo "API Docs:   http://localhost:8000/docs"

stop:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-web:
	docker-compose logs -f web

logs-worker:
	docker-compose logs -f browser-worker

migrate:
	docker-compose exec api alembic upgrade head

test:
	docker-compose exec api pytest tests/ -v
	cd apps/web && npm test

clean:
	docker-compose down -v
	rm -rf storage/screenshots/*
	rm -rf storage/resumes/*
	@echo "Cleaned containers, volumes, and storage"

shell-api:
	docker-compose exec api bash

shell-db:
	docker-compose exec postgres psql -U postgres -d job_automation

worker-start:
	docker-compose --profile worker up -d browser-worker

worker-stop:
	docker-compose --profile worker stop browser-worker
