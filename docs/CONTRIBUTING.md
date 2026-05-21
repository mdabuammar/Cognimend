# Contributing

Thanks for helping improve Cognimend. This project is focused on a simple document assistant experience: users upload documents, ask questions, and receive source-grounded answers with Trust Engine signals.

## Development Principles

- Keep the product focused on document Q&A and answer trust.
- Prefer clear, source-aware behavior over broad feature expansion.
- Do not add secrets, tokens, passwords, or local machine paths to committed files.
- Keep documentation factual and current.
- Add or update tests when behavior changes.

## Local Setup

Install the frontend dependencies:

```bash
cd frontend
npm install
```

Start supporting services with Docker Compose:

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

Configure local environment values in `.env`:

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>
JWT_SECRET=<your-jwt-secret>
```

## Checks

Run the relevant checks before opening a change:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

```bash
python -m py_compile backend/services/upload/main.py backend/services/query/main.py backend/services/query/trust_engine.py backend/services/telemetry/main.py
pytest backend/tests/test_trust_engine.py -v
pytest backend/tests/test_controller_evidence_aware.py -v
pytest backend/services/controller/tests/test_controller.py -v
```

## Pull Requests

Keep pull requests focused and describe the user-visible or operational impact. Include test results, note any skipped checks, and call out changes that affect document access, citation handling, Trust Engine behavior, or telemetry.

## Documentation

Update documentation when setup, endpoints, Trust Engine behavior, or deployment steps change. Keep archived material historical; active documentation should describe the current product only.
