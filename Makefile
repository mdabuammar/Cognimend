SHELL := powershell.exe
.PHONY: dev test migrate seed build up down logs

dev:
	cd backend && docker compose up -d postgres qdrant redis
	@echo "Infrastructure running. Start services individually or use 'make up'"

up:
	cd backend && docker compose up --build -d
	cd frontend && npm run dev

down:
	cd backend && docker compose down

build:
	cd backend && docker compose build

migrate:
	cd backend && Get-Content ..\database\migrations\001_initial_schema.sql, ..\database\migrations\002_performance_indexes.sql, ..\database\migrations\003_scaling_optimizations.sql, ..\database\migrations\004_saas_schema.sql | docker exec -i cognimend-postgres psql -U postgres -d cognimend

seed:
	cd backend && Get-Content scripts\seed_plans.sql | docker exec -i cognimend-postgres psql -U postgres -d cognimend

test:
	cd backend && python -m pytest tests/ -v

logs:
	cd backend && docker compose logs -f --tail=100
