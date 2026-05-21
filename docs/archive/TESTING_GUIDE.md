# Manual Testing Guide

## Prerequisites

1. **Docker Desktop** must be installed and running
2. **Python 3.8+** installed
3. **OpenAI API Key** - Update `backend/.env` with your actual key

## Step 1: Start Infrastructure Services

Open PowerShell in `D:\Project\backend`:

```powershell
cd D:\Project\backend

# Start all Docker services (PostgreSQL, Qdrant, Redis)
docker compose up -d

# Verify services are running
docker ps

# Check logs if needed
docker compose logs -f
```

**Expected:** 3 containers running (cognimend-postgres, cognimend-qdrant, cognimend-redis)

## Step 2: Start Upload Service

Open a **new PowerShell terminal**:

```powershell
cd D:\Project\backend\services\upload

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the service
python main.py
```

**Expected output:** 
```
✅ Upload Service initialized
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Keep this terminal open!**

## Step 3: Start Query Service

Open **another new PowerShell terminal**:

```powershell
cd D:\Project\backend\services\query

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the service
python main.py
```

**Expected output:**
```
✅ Query Service initialized
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8002
```

**Keep this terminal open!**

## Step 4: Test the Services

Open **another PowerShell terminal** for testing:

### Test 1: Upload a Document

First, create a test PDF or use an existing one. Then:

```powershell
# Navigate to directory with your PDF file
cd D:\Project  # or wherever your test.pdf is

# Upload the document
curl.exe -X POST http://localhost:8001/upload `
  -F "file=@test.pdf" `
  -F "title=Company Policy"
```

**Alternative using Invoke-WebRequest (PowerShell native):**

```powershell
$filePath = "D:\Project\test.pdf"  # Update with your file path
$uri = "http://localhost:8001/upload"

$form = @{
    file = Get-Item -Path $filePath
    title = "Company Policy"
}

Invoke-RestMethod -Uri $uri -Method Post -Form $form
```

**Expected Response:**
```json
{
  "success": true,
  "document_id": 1,
  "filename": "test.pdf",
  "title": "Company Policy",
  "version": 1,
  "chunks": 15,
  "status": "ready",
  "message": "✓ Document processed successfully with 15 chunks"
}
```

### Test 2: List Documents

```powershell
# Using curl
curl.exe http://localhost:8001/documents

# Using PowerShell
Invoke-RestMethod -Uri "http://localhost:8001/documents"
```

**Expected Response:**
```json
{
  "documents": [
    {
      "id": 1,
      "title": "Company Policy",
      "filename": "test.pdf",
      "version": 1,
      "status": "ready",
      "created_at": "2024-01-15T10:00:00",
      "chunk_count": 15
    }
  ]
}
```

### Test 3: Query Documents

```powershell
# Using curl
curl.exe -X POST http://localhost:8002/query `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What is the leave policy?\"}'

# Using PowerShell
$body = @{
    question = "What is the leave policy?"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

**Expected Response:**
```json
{
  "answer": "Based on the Company Policy document...",
  "confidence": 85.5,
  "citations": [
    {
      "document_id": 1,
      "title": "Company Policy",
      "snippet": "The leave policy states that...",
      "similarity": 92.3,
      "version": 1
    }
  ],
  "latency_ms": 1234,
  "retrieved_count": 3
}
```

### Test 4: Get Metrics

```powershell
# Using curl
curl.exe http://localhost:8002/metrics

# Using PowerShell
Invoke-RestMethod -Uri "http://localhost:8002/metrics"
```

**Expected Response:**
```json
{
  "total_queries": 1,
  "avg_confidence": 85.5,
  "avg_latency_ms": 1234,
  "last_query_at": "2024-01-15T10:05:00"
}
```

## Troubleshooting

### Issue: "Connection refused" or "Cannot connect"
- **Check:** Are both services running? Check the terminals where you started them.
- **Check:** Are Docker containers running? Run `docker ps`

### Issue: "Module not found"
- **Solution:** Install dependencies: `pip install -r requirements.txt`

### Issue: "OpenAI API key error"
- **Solution:** Update `backend/.env` with your actual OpenAI API key

### Issue: "Database connection error"
- **Check:** Is PostgreSQL container running? `docker ps | findstr postgres`
- **Check:** Wait a few seconds after starting Docker - services need time to initialize

### Issue: "Qdrant connection error"
- **Check:** Is Qdrant container running? `docker ps | findstr qdrant`
- **Check:** Wait for Qdrant to fully start (check logs: `docker compose logs qdrant`)

## Quick Health Checks

```powershell
# Check upload service
Invoke-RestMethod -Uri "http://localhost:8001/health"

# Check query service
Invoke-RestMethod -Uri "http://localhost:8002/health"
```

Both should return:
```json
{
  "status": "healthy",
  "service": "upload" or "query",
  "timestamp": "2024-01-15T10:00:00"
}
```
