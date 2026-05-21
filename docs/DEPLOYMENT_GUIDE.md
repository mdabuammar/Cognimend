# Deployment Guide

Cognimend can be run locally with Docker Compose for development and staging-style testing.

## Prerequisites

- Docker and Docker Compose
- Node.js 18 or newer
- Python 3.11 or newer
- OpenRouter API key

## Environment

Create a local environment file:

```bash
cp .env.example .env
```

Set at least:

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>
```

## Start Services

From the repository root:

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

Useful local service URLs:

- Frontend dev server: `http://localhost:5173`
- API gateway: `http://localhost:8080`
- Auth service: `http://localhost:8000`
- Upload service: `http://localhost:8001`
- Query service: `http://localhost:8002`
- Telemetry service: `http://localhost:8003`
- Drift detector: `http://localhost:8004`
- Controller service: `http://localhost:8005`
- Evaluation service: `http://localhost:8006`
- Qdrant: `http://localhost:6333`
- Grafana: `http://localhost:3000`
- Jaeger: `http://localhost:16686`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Health Checks

```bash
curl http://localhost:8002/health
curl http://localhost:8003/health
```

## Notes

OpenRouter errors caused by missing keys, rate limits, model availability, or account credits should not crash `/query`. The query service falls back to conservative source-based responses when possible.
