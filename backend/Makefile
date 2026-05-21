.PHONY: build up down logs clean test health restart

help:
	@echo "Cognimend Autonomous RAG System"
	@echo ""
	@echo "Available commands:"
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services (keeps data)"
	@echo "  make logs       - View live logs from all services"
	@echo "  make health     - Check health of all services"
	@echo "  make restart    - Restart all services"
	@echo "  make clean      - Remove all data and containers"
	@echo "  make test       - Run a test query"
	@echo ""

build:
	@echo "Building Docker images..."
	docker-compose build

up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make health

down:
	@echo "Stopping all services..."
	docker-compose down

logs:
	docker-compose logs -f

health:
	@echo ""
	@echo "Service Health Check:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@curl -s http://localhost:8001/health 2>/dev/null | jq '.service' || echo "❌ Upload"
	@curl -s http://localhost:8002/health 2>/dev/null | jq '.service' || echo "❌ Query"
	@curl -s http://localhost:8003/health 2>/dev/null | jq '.service' || echo "❌ Telemetry"
	@curl -s http://localhost:8004/health 2>/dev/null | jq '.service' || echo "❌ Drift Detector"
	@curl -s http://localhost:8005/health 2>/dev/null | jq '.service' || echo "❌ Controller"
	@curl -s http://localhost:8006/health 2>/dev/null | jq '.service' || echo "❌ Evaluation"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""

restart: down up

clean:
	@echo "Removing all containers and data..."
	docker-compose down -v
	@echo "Cleanup complete"

test:
	@echo "Testing Query Service..."
	curl -X POST http://localhost:8002/query \
		-H "Content-Type: application/json" \
		-d '{"question": "test query"}'

ps:
	docker-compose ps

shell-upload:
	docker-compose exec upload /bin/bash

shell-query:
	docker-compose exec query /bin/bash

shell-postgres:
	docker-compose exec postgres psql -U postgres -d cognimend

.DEFAULT_GOAL := help
