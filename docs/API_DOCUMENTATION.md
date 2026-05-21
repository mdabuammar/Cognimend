# API Documentation

This document lists the main service endpoints used by the current Cognimend document assistant.

## Auth Service

- `GET /health`
- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /auth/google/start`
- `GET /auth/google/callback`

## Upload Service

- `POST /upload`
- `GET /documents`
- `GET /documents/{doc_id}`
- `GET /documents/{doc_id}/download`
- `POST /documents/{doc_id}/reindex`
- `POST /documents/reindex-all`
- `GET /health`
- `GET /metrics`

## Query Service

- `POST /query`
- `POST /query/with-file`
- `GET /history`
- `GET /history/{query_id}`
- `GET /metrics`
- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/startup`

## Telemetry and RAG Health

- `GET /dashboard/stats`
- `GET /dashboard/trends`
- `GET /dashboard/recent-queries`
- `GET /dashboard/faithfulness`
- `GET /dashboard/retrieval-quality`
- `GET /dashboard/citation-quality`
- `GET /dashboard/query-drift`
- `GET /dashboard/rag-quality`
- `GET /health`

## Drift, Controller, and Evaluation

Drift detector:

- `POST /run-detection`
- `GET /detectors`
- `GET /status`
- `GET /history`
- `GET /health`

Controller:

- `GET /repair-candidates`
- `POST /repair-candidates/{candidate_id}/test`
- `POST /repair-candidates/{candidate_id}/apply`
- `POST /repair-candidates/{candidate_id}/reject`
- `POST /config/rollback`
- `GET /config/history`
- `GET /health`

Evaluation:

- `GET /questions`
- `POST /questions`
- `POST /repair-candidate/{candidate_id}/run`
- `GET /repair-candidate/{candidate_id}/result`
- `GET /health`
