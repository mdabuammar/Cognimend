# 📚 Cognimend API Documentation

> Complete API reference for all Cognimend microservices

**Version:** 2.0.0  
**Base URLs:**
- Upload Service: `http://localhost:8001`
- Query Service: `http://localhost:8002`
- Telemetry Service: `http://localhost:8003`
- Drift Detector: `http://localhost:8004`
- Controller: `http://localhost:8005`
- Evaluation: `http://localhost:8006`

---

## Table of Contents

- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Upload Service](#upload-service)
- [Query Service](#query-service)
- [Telemetry Service](#telemetry-service)
- [Drift Detector](#drift-detector)
- [Controller Service](#controller-service)
- [Evaluation Service](#evaluation-service)
- [WebSocket API](#websocket-api)
- [OpenAPI Specification](#openapi-specification)

---

## Authentication

All API requests require authentication using an API key passed in the header.

### Request Header

```http
X-API-Key: your-api-key
```

### Authentication Errors

| Status | Error | Description |
|--------|-------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid API key |
| 403 | `FORBIDDEN` | API key lacks required permissions |

### Example

```bash
curl -X GET http://localhost:8002/health \
  -H "X-API-Key: your-api-key"
```

---

## Rate Limiting

API requests are rate-limited per API key.

| Tier | Requests/min | Burst |
|------|--------------|-------|
| Free | 60 | 10 |
| Pro | 600 | 50 |
| Enterprise | 6000 | 200 |

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706745600
```

### Rate Limit Error

```json
{
  "error": "RATE_LIMITED",
  "message": "Too many requests",
  "retry_after": 30
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human readable message",
  "detail": "Additional context (optional)",
  "request_id": "req_abc123",
  "timestamp": "2024-01-31T12:00:00Z"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Upload Service

Base URL: `http://localhost:8001`

### POST /upload

Upload a document for processing and indexing.

#### Request

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Yes | API authentication key |
| `Content-Type` | Yes | `multipart/form-data` |
| `X-Request-ID` | No | Custom request identifier |

**Body (multipart/form-data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Document file (PDF, DOCX, TXT) |
| `metadata` | JSON | No | Custom metadata object |

**Constraints:**
- Max file size: 50MB
- Allowed types: `.pdf`, `.docx`, `.txt`

#### Response

**Success (201 Created):**
```json
{
  "document_id": "doc_abc123def456",
  "filename": "employee_handbook.pdf",
  "file_hash": "sha256:a1b2c3d4...",
  "chunks": 42,
  "status": "processed",
  "processing_time_ms": 2340,
  "metadata": {
    "pages": 15,
    "word_count": 8500,
    "language": "en"
  },
  "created_at": "2024-01-31T12:00:00Z"
}
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | `INVALID_FILE_TYPE` | Unsupported file format |
| 400 | `EMPTY_DOCUMENT` | File contains no extractable text |
| 409 | `DUPLICATE_DOCUMENT` | Document with same hash exists |
| 413 | `FILE_TOO_LARGE` | File exceeds 50MB limit |
| 422 | `EXTRACTION_FAILED` | Could not parse document |
| 500 | `VECTOR_STORE_ERROR` | Failed to store embeddings |

#### Examples

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8001/upload \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf" \
  -F 'metadata={"department": "HR", "version": "2.0"}'
```
</details>

<details>
<summary><b>Python (requests)</b></summary>

```python
import requests
import json

url = "http://localhost:8001/upload"
headers = {"X-API-Key": "your-api-key"}

with open("document.pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    data = {"metadata": json.dumps({"department": "HR"})}
    
    response = requests.post(url, headers=headers, files=files, data=data)
    
if response.status_code == 201:
    result = response.json()
    print(f"Document ID: {result['document_id']}")
    print(f"Chunks created: {result['chunks']}")
else:
    print(f"Error: {response.json()['error']}")
```
</details>

<details>
<summary><b>JavaScript (fetch)</b></summary>

```javascript
async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('metadata', JSON.stringify({ department: 'HR' }));

  const response = await fetch('http://localhost:8001/upload', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your-api-key'
    },
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message);
  }

  return await response.json();
}
```
</details>

<details>
<summary><b>Go (net/http)</b></summary>

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

func uploadDocument(filepath string) error {
    file, err := os.Open(filepath)
    if err != nil {
        return err
    }
    defer file.Close()

    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)
    
    part, err := writer.CreateFormFile("file", filepath)
    if err != nil {
        return err
    }
    io.Copy(part, file)
    writer.Close()

    req, err := http.NewRequest("POST", "http://localhost:8001/upload", body)
    if err != nil {
        return err
    }
    
    req.Header.Set("Content-Type", writer.FormDataContentType())
    req.Header.Set("X-API-Key", "your-api-key")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Printf("Document ID: %s\n", result["document_id"])
    
    return nil
}
```
</details>

---

### GET /documents

List all uploaded documents.

#### Request

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page (max 100) |
| `sort` | string | `created_at` | Sort field |
| `order` | string | `desc` | Sort order (`asc`, `desc`) |
| `status` | string | - | Filter by status |

#### Response

**Success (200 OK):**
```json
{
  "documents": [
    {
      "document_id": "doc_abc123",
      "filename": "employee_handbook.pdf",
      "status": "processed",
      "chunks": 42,
      "created_at": "2024-01-31T12:00:00Z",
      "updated_at": "2024-01-31T12:00:05Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 47,
    "pages": 3
  }
}
```

---

### GET /documents/{document_id}

Get details of a specific document.

#### Response

**Success (200 OK):**
```json
{
  "document_id": "doc_abc123",
  "filename": "employee_handbook.pdf",
  "file_hash": "sha256:a1b2c3d4...",
  "status": "processed",
  "chunks": 42,
  "metadata": {
    "pages": 15,
    "word_count": 8500,
    "language": "en",
    "custom": {}
  },
  "versions": [
    {
      "version": 2,
      "created_at": "2024-01-31T12:00:00Z",
      "chunks": 42
    },
    {
      "version": 1,
      "created_at": "2024-01-15T10:00:00Z",
      "chunks": 40
    }
  ],
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-31T12:00:00Z"
}
```

**Error (404 Not Found):**
```json
{
  "error": "NOT_FOUND",
  "message": "Document not found",
  "document_id": "doc_invalid"
}
```

---

### DELETE /documents/{document_id}

Delete a document and its vectors.

#### Request

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `version` | int | - | Delete specific version only |

#### Response

**Success (200 OK):**
```json
{
  "document_id": "doc_abc123",
  "status": "deleted",
  "chunks_removed": 42,
  "deleted_at": "2024-01-31T12:00:00Z"
}
```

---

## Query Service

Base URL: `http://localhost:8002`

### POST /query

Query the RAG system with a natural language question.

#### Request

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Yes | API authentication key |
| `Content-Type` | Yes | `application/json` |

**Body (JSON):**
```json
{
  "query": "What is the vacation policy?",
  "top_k": 5,
  "include_sources": true,
  "min_confidence": 0.5,
  "document_ids": ["doc_abc123"],
  "stream": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | - | Natural language question |
| `top_k` | int | No | 5 | Number of documents to retrieve |
| `include_sources` | bool | No | true | Include source citations |
| `min_confidence` | float | No | 0.0 | Minimum confidence threshold |
| `document_ids` | array | No | [] | Filter to specific documents |
| `stream` | bool | No | false | Enable streaming response |

#### Response

**Success (200 OK):**
```json
{
  "answer": "Based on the Employee Handbook, full-time employees receive 20 days of paid time off per year...",
  "confidence": 0.92,
  "sources": [
    {
      "document_id": "doc_abc123",
      "document_name": "Employee Handbook 2024",
      "chunk_id": "chunk_xyz789",
      "snippet": "Full-time employees are entitled to 20 days of paid time off...",
      "similarity": 0.95,
      "page": 42
    }
  ],
  "metadata": {
    "query_id": "qry_abc123",
    "response_time_ms": 1250,
    "documents_searched": 47,
    "cached": false,
    "model": "claude-3-haiku",
    "tokens_used": 450
  }
}
```

**Streaming Response (SSE):**
```
data: {"type": "chunk", "content": "Based on "}
data: {"type": "chunk", "content": "the Employee "}
data: {"type": "chunk", "content": "Handbook..."}
data: {"type": "sources", "sources": [...]}
data: {"type": "done", "metadata": {...}}
```

#### Examples

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "What is the vacation policy?",
    "top_k": 5,
    "include_sources": true
  }'
```
</details>

<details>
<summary><b>Python (requests)</b></summary>

```python
import requests

url = "http://localhost:8002/query"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key"
}
payload = {
    "query": "What is the vacation policy?",
    "top_k": 5,
    "include_sources": True
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']:.0%}")
print(f"Response time: {result['metadata']['response_time_ms']}ms")

for source in result['sources']:
    print(f"  - {source['document_name']} (similarity: {source['similarity']:.0%})")
```
</details>

<details>
<summary><b>Python (streaming)</b></summary>

```python
import requests
import json

url = "http://localhost:8002/query"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key"
}
payload = {
    "query": "What is the vacation policy?",
    "stream": True
}

with requests.post(url, headers=headers, json=payload, stream=True) as response:
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8').replace('data: ', ''))
            if data['type'] == 'chunk':
                print(data['content'], end='', flush=True)
            elif data['type'] == 'done':
                print(f"\n\nTokens used: {data['metadata']['tokens_used']}")
```
</details>

<details>
<summary><b>JavaScript (fetch)</b></summary>

```javascript
async function queryRAG(question) {
  const response = await fetch('http://localhost:8002/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
      query: question,
      top_k: 5,
      include_sources: true
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  
  console.log(`Answer: ${data.answer}`);
  console.log(`Confidence: ${(data.confidence * 100).toFixed(0)}%`);
  
  return data;
}
```
</details>

<details>
<summary><b>Go (net/http)</b></summary>

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type QueryRequest struct {
    Query          string   `json:"query"`
    TopK           int      `json:"top_k"`
    IncludeSources bool     `json:"include_sources"`
    DocumentIDs    []string `json:"document_ids,omitempty"`
}

type QueryResponse struct {
    Answer     string  `json:"answer"`
    Confidence float64 `json:"confidence"`
    Sources    []struct {
        DocumentName string  `json:"document_name"`
        Similarity   float64 `json:"similarity"`
    } `json:"sources"`
}

func queryRAG(question string) (*QueryResponse, error) {
    payload := QueryRequest{
        Query:          question,
        TopK:           5,
        IncludeSources: true,
    }
    
    body, _ := json.Marshal(payload)
    
    req, _ := http.NewRequest("POST", "http://localhost:8002/query", bytes.NewBuffer(body))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("X-API-Key", "your-api-key")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result QueryResponse
    json.NewDecoder(resp.Body).Decode(&result)
    
    return &result, nil
}
```
</details>

---

### GET /metrics/prometheus

Get Prometheus-formatted metrics.

#### Response

**Success (200 OK):**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/query",status="200"} 1234

# HELP query_latency_seconds Query latency histogram
# TYPE query_latency_seconds histogram
query_latency_seconds_bucket{le="0.5"} 100
query_latency_seconds_bucket{le="1"} 200
query_latency_seconds_bucket{le="2"} 350

# HELP cache_hit_rate Cache hit ratio
# TYPE cache_hit_rate gauge
cache_hit_rate 0.82
```

---

### GET /health

Health check endpoint.

#### Response

**Success (200 OK):**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime_seconds": 86400,
  "checks": {
    "database": "healthy",
    "qdrant": "healthy",
    "redis": "healthy",
    "openrouter": "healthy"
  }
}
```

**Degraded (200 OK):**
```json
{
  "status": "degraded",
  "version": "2.0.0",
  "checks": {
    "database": "healthy",
    "qdrant": "healthy",
    "redis": "unhealthy",
    "openrouter": "healthy"
  }
}
```

---

## Telemetry Service

Base URL: `http://localhost:8003`

### GET /dashboard/stats

Get aggregated dashboard statistics.

#### Response

**Success (200 OK):**
```json
{
  "stats": {
    "total_queries": 12345,
    "total_documents": 47,
    "avg_confidence": 0.873,
    "avg_response_time_ms": 1250,
    "cache_hit_rate": 0.82,
    "queries_today": 234,
    "queries_this_week": 1580
  },
  "trends": {
    "queries_7d": [145, 167, 189, 203, 198, 234, 444],
    "confidence_7d": [0.85, 0.86, 0.87, 0.88, 0.86, 0.87, 0.87],
    "latency_7d": [1300, 1280, 1250, 1220, 1240, 1260, 1250]
  },
  "updated_at": "2024-01-31T12:00:00Z"
}
```

---

### GET /dashboard/drift

Get current drift detection status.

#### Response

**Success (200 OK):**
```json
{
  "drift_status": {
    "data_drift": {
      "status": "ok",
      "score": 0.08,
      "threshold": 0.15,
      "last_checked": "2024-01-31T11:55:00Z"
    },
    "retrieval_drift": {
      "status": "warning",
      "score": 0.12,
      "threshold": 0.10,
      "last_checked": "2024-01-31T11:55:00Z"
    },
    "performance_drift": {
      "status": "ok",
      "score": 0.02,
      "threshold": 0.05,
      "last_checked": "2024-01-31T11:55:00Z"
    }
  },
  "overall_status": "warning",
  "last_remediation": "2024-01-30T15:30:00Z"
}
```

---

### GET /dashboard/recent-queries

Get recent query history.

#### Request

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 10 | Number of queries (max 100) |
| `offset` | int | 0 | Pagination offset |

#### Response

**Success (200 OK):**
```json
{
  "queries": [
    {
      "query_id": "qry_abc123",
      "query": "What is the vacation policy?",
      "confidence": 0.92,
      "response_time_ms": 1250,
      "cached": false,
      "created_at": "2024-01-31T11:59:30Z"
    }
  ],
  "total": 12345,
  "limit": 10,
  "offset": 0
}
```

---

## Drift Detector

Base URL: `http://localhost:8004`

### GET /status

Get current drift detection status.

#### Response

**Success (200 OK):**
```json
{
  "service": "drift-detector",
  "version": "2.0.0",
  "status": "running",
  "last_check": "2024-01-31T11:55:00Z",
  "next_check": "2024-01-31T12:00:00Z",
  "drift_types": {
    "data_drift": {
      "enabled": true,
      "status": "ok",
      "ks_statistic": 0.08,
      "p_value": 0.42,
      "threshold": 0.15
    },
    "retrieval_drift": {
      "enabled": true,
      "status": "warning",
      "score": 0.12,
      "threshold": 0.10
    },
    "performance_drift": {
      "enabled": true,
      "status": "ok",
      "confidence_change": -0.02,
      "latency_change": 0.05,
      "threshold": 0.05
    }
  }
}
```

---

### POST /detect

Trigger manual drift detection.

#### Request

**Body (JSON):**
```json
{
  "types": ["data", "retrieval", "performance"],
  "window_hours": 24
}
```

#### Response

**Success (200 OK):**
```json
{
  "detection_id": "det_abc123",
  "status": "completed",
  "results": {
    "data_drift": {
      "detected": false,
      "ks_statistic": 0.08,
      "p_value": 0.42
    },
    "retrieval_drift": {
      "detected": true,
      "score": 0.12,
      "samples_analyzed": 1000
    },
    "performance_drift": {
      "detected": false,
      "confidence_change": -0.02
    }
  },
  "duration_ms": 2500
}
```

---

## Controller Service

Base URL: `http://localhost:8005`

### GET /status

Get controller status and configuration.

#### Response

**Success (200 OK):**
```json
{
  "service": "controller",
  "version": "2.0.0",
  "status": "running",
  "config": {
    "version": 5,
    "updated_at": "2024-01-31T10:00:00Z",
    "auto_heal_enabled": true,
    "check_interval_seconds": 300
  },
  "circuit_breakers": {
    "openrouter": "closed",
    "qdrant": "closed",
    "postgres": "closed"
  }
}
```

---

### POST /trigger-check

Trigger manual system check.

#### Response

**Success (200 OK):**
```json
{
  "check_id": "chk_abc123",
  "status": "completed",
  "results": {
    "drift_check": "passed",
    "health_check": "passed",
    "resource_check": "passed"
  },
  "actions_taken": [],
  "duration_ms": 1500
}
```

---

### GET /actions/history

Get history of auto-healing actions.

#### Request

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Number of actions |
| `status` | string | - | Filter by status |

#### Response

**Success (200 OK):**
```json
{
  "actions": [
    {
      "action_id": "act_abc123",
      "type": "reindex",
      "trigger": "retrieval_drift",
      "status": "completed",
      "started_at": "2024-01-30T15:30:00Z",
      "completed_at": "2024-01-30T15:35:00Z",
      "result": {
        "documents_reindexed": 5,
        "drift_score_before": 0.18,
        "drift_score_after": 0.06
      }
    }
  ],
  "total": 15
}
```

---

## Evaluation Service

Base URL: `http://localhost:8006`

### POST /evaluate

Run evaluation benchmark.

#### Request

**Body (JSON):**
```json
{
  "test_questions": [
    {
      "question": "What is the vacation policy?",
      "expected_keywords": ["20 days", "paid time off"],
      "min_confidence": 0.8
    }
  ],
  "run_all": false
}
```

#### Response

**Success (200 OK):**
```json
{
  "evaluation_id": "eval_abc123",
  "status": "completed",
  "results": {
    "total_questions": 10,
    "passed": 9,
    "failed": 1,
    "avg_confidence": 0.87,
    "avg_latency_ms": 1250
  },
  "details": [
    {
      "question": "What is the vacation policy?",
      "passed": true,
      "confidence": 0.92,
      "latency_ms": 1100,
      "keywords_found": ["20 days", "paid time off"]
    }
  ],
  "duration_ms": 15000
}
```

---

### GET /benchmarks

Get benchmark history.

#### Response

**Success (200 OK):**
```json
{
  "benchmarks": [
    {
      "evaluation_id": "eval_abc123",
      "created_at": "2024-01-31T12:00:00Z",
      "pass_rate": 0.90,
      "avg_confidence": 0.87,
      "avg_latency_ms": 1250
    }
  ],
  "total": 25
}
```

---

## WebSocket API

### Real-time Query Streaming

**Endpoint:** `ws://localhost:8002/ws/query`

**Connect:**
```javascript
const ws = new WebSocket('ws://localhost:8002/ws/query?api_key=your-key');

ws.onopen = () => {
  ws.send(JSON.stringify({
    query: "What is the vacation policy?",
    top_k: 5
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'chunk':
      process.stdout.write(data.content);
      break;
    case 'sources':
      console.log('Sources:', data.sources);
      break;
    case 'done':
      console.log('Complete!', data.metadata);
      ws.close();
      break;
  }
};
```

### Real-time Metrics

**Endpoint:** `ws://localhost:8003/ws/metrics`

**Events:**
```json
{"type": "query", "data": {"query_id": "...", "confidence": 0.92}}
{"type": "drift", "data": {"type": "retrieval", "score": 0.12}}
{"type": "action", "data": {"type": "reindex", "status": "started"}}
```

---

## OpenAPI Specification

Full OpenAPI 3.0 specifications are available at:

- Upload: `http://localhost:8001/openapi.json`
- Query: `http://localhost:8002/openapi.json`
- Telemetry: `http://localhost:8003/openapi.json`
- Drift Detector: `http://localhost:8004/openapi.json`
- Controller: `http://localhost:8005/openapi.json`
- Evaluation: `http://localhost:8006/openapi.json`

Interactive Swagger UI: `http://localhost:{port}/docs`

---

## SDK Libraries

Official SDK libraries coming soon:

- [ ] Python SDK (`pip install cognimend`)
- [ ] JavaScript/TypeScript SDK (`npm install @cognimend/sdk`)
- [ ] Go SDK (`go get github.com/cognimend/go-sdk`)

---

## Changelog

### v2.0.0 (2024-01-31)
- Added streaming responses
- Added WebSocket API
- Added rate limiting
- Added circuit breakers
- Improved error responses

### v1.0.0 (2024-01-15)
- Initial release
