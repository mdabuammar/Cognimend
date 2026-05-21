# Cognimend

Cognimend is an AI document assistant that lets users upload documents, ask questions, and receive source-grounded answers. Behind the simple interface, Cognimend includes a Trust Engine that verifies answer quality, checks citations, detects conflicts, identifies missing evidence, and monitors RAG health over time.

The product is intentionally straightforward: sign in, add documents, ask questions, and review answers with their sources and trust signals.

## Overview

Cognimend is built for teams and individuals who need to query their own documents without losing track of where an answer came from. It combines document upload, vector search, source citations, and answer verification in one workflow.

The main goal is not to replace review or judgment. The goal is to make document Q&A more transparent by showing sources, highlighting uncertainty, and refusing to invent details when the uploaded material does not support an answer.

## Key Features

- User authentication and workspace-aware access
- Document upload and processing
- PDF, DOCX, TXT, MD, and DOC upload support
- Chat with uploaded documents
- Source citations for generated answers
- Answer Trust badge for quick review
- Claim Passport for claim-level support checks
- Strict Evidence Mode for conservative answers
- Citation Truth Score for citation quality
- Conflict Detection across retrieved sources
- Evidence Gap Detection when documents are missing key facts
- Freshness Awareness for dated or versioned sources
- RAG Health Timeline with live quality events
- Evidence-aware self-healing repair suggestions
- Dashboard and analytics for answer and retrieval quality

## Trust Engine

Cognimend's Trust Engine runs behind the document chat experience. It checks whether answers are supported by the user's documents and adds clear signals when confidence is limited.

The Trust Engine currently includes:

- Claim Passport: breaks an answer into claims and checks source support.
- Strict Evidence Mode: refuses or narrows answers when evidence is not strong enough.
- Citation Truth Score: scores whether cited chunks actually support the answer.
- Conflict Detection: identifies conflicting facts across retrieved documents.
- Evidence Gap Detection: flags questions that cannot be answered from available sources.
- Freshness Awareness: warns when source dates or versions matter.
- RAG Quality Monitoring: records query quality signals over time.
- Statistical Drift Detection: tracks changes in retrieval and answer quality.
- Rollback-safe configuration: protects stable settings when repairs fail.
- Honest repair rejection: failed repair candidates are rejected instead of applied.
- RAG Health Timeline: shows recent quality events from live query telemetry.

These checks are designed to make answer quality visible without adding complexity to the main user flow.

## Architecture

```text
Frontend
  -> API Gateway
  -> Auth / Upload / Query / Telemetry / Drift / Controller / Evaluation
  -> PostgreSQL / Qdrant / Redis
  -> OpenRouter
```

PostgreSQL stores metadata, users, query history, telemetry, and Trust Engine records. Qdrant stores document vectors for semantic search. Redis is used for caching and service support where available. OpenRouter provides LLM and embedding access. The telemetry, drift, controller, and evaluation services support the Trust Engine's monitoring and repair workflow.

## Core User Flow

```text
Sign up
  -> Upload documents
  -> Ask questions
  -> Get answers with sources
  -> Review trust signals
  -> Monitor RAG health
```

## Tech Stack

Frontend:

- React
- TypeScript
- Vite
- Tailwind CSS
- React Query

Backend:

- FastAPI
- PostgreSQL
- Qdrant
- Redis
- RabbitMQ
- OpenRouter

DevOps and monitoring:

- Docker Compose
- Prometheus
- Grafana
- Jaeger

## Project Structure

```text
backend/
  services/
    auth/
    gateway/
    upload/
    query/
    telemetry/
    drift_detector/
    controller/
    evaluation/
    faithfulness_verifier/
    shared/
database/
  migrations/
docs/
  archive/
frontend/
  src/
k8s/
tests/
```

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer
- Docker and Docker Compose
- OpenRouter API key

PostgreSQL, Qdrant, Redis, RabbitMQ, Prometheus, Grafana, and Jaeger can be started through Docker Compose.

### Environment Setup

Copy an example environment file and set your local values:

```bash
cp .env.example .env
```

At minimum, configure:

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>
```

Keep API keys and passwords in environment files or secret managers. Do not commit secrets.

### Start Backend Services

From the repository root:

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

For local Python service startup during development:

```bash
python start_services.py
```

### Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs locally and talks to the configured backend service URLs.

## Running Tests

Frontend checks:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

Backend checks:

```bash
python -m py_compile backend/services/upload/main.py backend/services/query/main.py backend/services/query/trust_engine.py backend/services/telemetry/main.py
pytest backend/tests/test_trust_engine.py -v
pytest backend/tests/test_controller_evidence_aware.py -v
pytest backend/services/controller/tests/test_controller.py -v
```

## Current Status

Cognimend is a staging-ready product prototype focused on AI document Q&A and answer trust. The Trust Engine has been proof-tested in controlled live tests, with the most recent controlled proof score estimated at 96/100.

Known limitations:

- OpenRouter availability depends on a valid API key, model availability, rate limits, and account credits.
- Freshness awareness is strongest when uploaded documents include useful date or version metadata.
- Browser-based smoke testing still needs stronger automation coverage.
- Some archived documentation describes older directions and is kept only for historical reference.

## Roadmap

- Stronger browser smoke testing for the main user flows
- Support for more document types
- Google Drive connector
- Larger evaluation datasets
- Better deployment automation
- User feedback learning loop for answer quality

## Security Notes

- User and workspace context is included in document access checks.
- Qdrant retrieval is filtered by workspace and allowed document scope.
- Query cache keys include workspace, user permission context, question, top-k, and verifier mode.
- API keys should be stored in environment variables or secret managers only.
- No secrets should be committed to the repository.

## Documentation

- [Trust Engine](docs/TRUST_ENGINE.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Security Notes](docs/SECURITY.md)
- [Contributing](docs/CONTRIBUTING.md)
- Historical and outdated material is stored in [docs/archive](docs/archive).

## License

License: Not specified yet.
