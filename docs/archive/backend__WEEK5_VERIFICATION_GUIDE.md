# 📋 WEEK 5 COMPLETE VERIFICATION GUIDE

Comprehensive step-by-step checklist to verify your entire system from Week 1-5

---

## 🎯 OVERVIEW: WHAT WE'RE CHECKING

| Week | Component | What to Verify |
|------|-----------|---|
| **Week 1** | Frontend (Vercel) | Is it live? Can I access it? |
| **Week 2** | Backend Services | Upload & Query working? |
| **Week 3** | Drift Detection | Detecting 3 types of drift? |
| **Week 4** | Auto-Controller | Self-healing operational? |
| **Week 5** | Docker Compose + Testing | Everything containerized? |

---

## PRE-FLIGHT CHECK (5 minutes)

### Step 1: Check Your Project Structure

Open File Explorer and verify this structure exists:

```
D:\Project\
│
├── frontend\                              ← Week 1 code
│   ├── src\
│   ├── package.json
│   └── ... (React/TypeScript files)
│
└── backend\                               ← Week 2-5 code
    │
    ├── .env                               ← Your OpenAI API key
    ├── .dockerignore
    ├── docker-compose.yml                 ← Main file
    ├── Makefile
    ├── start.sh / start.bat
    ├── stop.sh
    ├── cleanup.sh
    │
    ├── test-docker-setup.ps1              ← Automated test script
    ├── test-docker-setup.sh
    │
    ├── TEST_CHECKLIST.md                  ← Testing guides
    ├── TESTING_QUICK_START.md
    ├── TESTING_GUIDE.md
    └── TESTING_COMPLETE.md
    │
    └── services\
        │
        ├── upload\
        │   ├── Dockerfile
        │   ├── main.py
        │   └── requirements.txt
        │
        ├── query\
        │   ├── Dockerfile
        │   ├── main.py
        │   └── requirements.txt
        │
        ├── telemetry\
        │   ├── Dockerfile
        │   ├── main.py
        │   └── requirements.txt
        │
        ├── drift_detector\
        │   ├── Dockerfile
        │   ├── main.py
        │   └── requirements.txt
        │
        ├── controller\
        │   ├── Dockerfile
        │   ├── main.py
        │   └── requirements.txt
        │
        └── evaluation\
            ├── Dockerfile
            ├── main.py
            └── requirements.txt
```

**✅ CHECK:**
- [ ] All folders exist
- [ ] All Dockerfiles present (6 total)
- [ ] All main.py files present (6 total)
- [ ] docker-compose.yml exists
- [ ] .env file exists

---

### Step 2: Verify Docker Installation

Open PowerShell and run:

```powershell
docker --version
docker-compose --version
```

**Expected Output:**

```
Docker version 24.0.x, build xxxxxx
Docker Compose version v2.x.x
```

**✅ CHECK:**
- [ ] Docker version shows
- [ ] Docker Compose version shows
- [ ] No error messages

**If not installed:**
1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install it
3. Restart computer
4. Start Docker Desktop
5. Run commands again

---

### Step 3: Verify OpenAI API Key

```powershell
cd D:\Project\backend

# View .env file
type .env
```

**Expected Content:**

```
OPENAI_API_KEY=<your-openrouter-api-key>
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<redacted-secret>
```

**✅ CHECK:**
- [ ] .env file exists
- [ ] OPENAI_API_KEY is set
- [ ] Database credentials present

**If missing:**
1. Create .env file in D:\Project\backend\
2. Get API key from: https://platform.openai.com/api-keys
3. Paste it in .env

---

## WEEK 1 VERIFICATION: FRONTEND (5 minutes)

### Step 4: Check Vercel Deployment

Open browser and visit:

```
https://cognimend-sand.vercel.app/
```

**Expected:** Your frontend UI loads

**✅ CHECK:**
- [ ] Website loads
- [ ] No 404 error
- [ ] Shows upload interface
- [ ] Shows query interface
- [ ] Shows dashboard

**If not working:**

```bash
# Clone from GitHub again
cd D:\Project
git clone https://github.com/mdabuammar/cognimend.git frontend
```

---

### Step 5: Verify Frontend Code Locally

```powershell
cd D:\Project\frontend

# Install dependencies
npm install

# Run locally
npm run dev
```

**Expected:** Opens at http://localhost:5173

**✅ CHECK:**
- [ ] npm install succeeds
- [ ] npm run dev starts
- [ ] Browser opens automatically
- [ ] UI looks good

Press Ctrl+C to stop.

---

## WEEK 2 VERIFICATION: RAG BACKEND (15 minutes)

### Step 6: Build Docker Images

```powershell
cd D:\Project\backend

# Build all images
docker-compose build
```

**Expected Output:**

```
[+] Building 234.5s (75/75) FINISHED
 => [upload internal] load build definition
 => [upload] resolving provenance
 => [query internal] load build definition
 => [query] resolving provenance
 ... (continues for all 6 services)
Successfully built
```

**✅ CHECK:**
- [ ] Build completes without errors
- [ ] All 6 services built (upload, query, telemetry, drift_detector, controller, evaluation)
- [ ] No "ERROR" messages

*This takes 5-10 minutes the first time.*

---

### Step 7: Start All Services

```powershell
docker-compose up -d
```

**Expected Output:**

```
[+] Running 10/10
 ✔ Network cognimend-network          Created
 ✔ Volume "backend_postgres_data"     Created
 ✔ Volume "backend_qdrant_data"       Created
 ✔ Volume "backend_redis_data"        Created
 ✔ Container cognimend-postgres       Started
 ✔ Container cognimend-qdrant         Started
 ✔ Container cognimend-redis          Started
 ✔ Container cognimend-upload         Started
 ✔ Container cognimend-query          Started
 ✔ Container cognimend-telemetry      Started
 ✔ Container cognimend-drift-detector Started
 ✔ Container cognimend-controller     Started
 ✔ Container cognimend-evaluation     Started
```

**✅ CHECK:**
- [ ] All 9 containers started
- [ ] No "Exited" status
- [ ] Network created
- [ ] Volumes created

---

### Step 8: Verify All Containers Running

```powershell
docker ps
```

**Expected:** 9 containers running

```
CONTAINER ID   IMAGE                     STATUS         PORTS
xxxxx          backend-upload            Up 2 minutes   0.0.0.0:8001->8001/tcp
xxxxx          backend-query             Up 2 minutes   0.0.0.0:8002->8002/tcp
xxxxx          backend-telemetry         Up 2 minutes   0.0.0.0:8003->8003/tcp
xxxxx          backend-drift_detector    Up 2 minutes   0.0.0.0:8004->8004/tcp
xxxxx          backend-controller        Up 2 minutes   0.0.0.0:8005->8005/tcp
xxxxx          backend-evaluation        Up 2 minutes   0.0.0.0:8006->8006/tcp
xxxxx          postgres:15-alpine        Up 2 minutes   0.0.0.0:5432->5432/tcp
xxxxx          qdrant/qdrant:latest      Up 2 minutes   0.0.0.0:6333->6333/tcp
xxxxx          redis:7-alpine            Up 2 minutes   0.0.0.0:6379->6379/tcp
```

**✅ CHECK:**
- [ ] 9 containers total
- [ ] All show "Up X minutes"
- [ ] None show "Restarting" or "Exited"

**If any failed:**

```powershell
# Check logs for that service
docker-compose logs <service-name>

# Example:
docker-compose logs upload
```

---

### Step 9: Health Check All Services

Wait 30 seconds for services to initialize, then:

```powershell
# Upload service
Invoke-WebRequest -Uri "http://localhost:8001/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List

# Query service
Invoke-WebRequest -Uri "http://localhost:8002/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List

# Telemetry service
Invoke-WebRequest -Uri "http://localhost:8003/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List

# Drift detector
Invoke-WebRequest -Uri "http://localhost:8004/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List

# Controller
Invoke-WebRequest -Uri "http://localhost:8005/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List

# Evaluation
Invoke-WebRequest -Uri "http://localhost:8006/health" -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected for EACH:**

```json
{
  "status": "healthy",
  "service": "upload",
  "timestamp": "2026-01-26T02:20:00"
}
```

**✅ CHECK:**
- [ ] All 6 services return "healthy"
- [ ] No connection errors
- [ ] Timestamps are current

---

### Step 10: Test Upload Functionality (Week 2 - Upload Service)

Create a test document:

```powershell
# Create test file
echo "Company Vacation Policy: Employees receive 15 days of paid vacation annually. Sick leave is 10 days per year. Remote work is allowed 2 days per week." > test_policy.txt
```

Upload it:

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8001/upload" `
  -Method Post `
  -Form @{
    file = Get-Item -Path "test_policy.txt"
    title = "Company Policy"
  } -ErrorAction SilentlyContinue

$response.Content | ConvertFrom-Json | Format-List
```

**Expected Response:**

```json
{
  "success": true,
  "document_id": 1,
  "filename": "test_policy.txt",
  "title": "Company Policy",
  "version": 1,
  "chunks": 1,
  "status": "ready",
  "message": "✓ Document processed successfully with 1 chunks"
}
```

**✅ CHECK:**
- [ ] "success": true
- [ ] Got document_id (note this number)
- [ ] status is "ready"
- [ ] chunks > 0

---

### Step 11: Test Query Functionality (Week 2 - Query Service)

```powershell
$query = @{
  question = "How many vacation days do employees get?"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8002/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body $query `
  -ErrorAction SilentlyContinue

$response.Content | ConvertFrom-Json | Format-List
```

**Expected Response:**

```json
{
  "answer": "Employees receive 15 days of paid vacation annually.",
  "confidence": 88.5,
  "citations": [
    {
      "document_id": 1,
      "title": "Company Policy",
      "snippet": "Employees receive 15 days of paid vacation annually...",
      "similarity": 92.3,
      "version": 1
    }
  ],
  "latency_ms": 1850,
  "retrieved_count": 1
}
```

**✅ CHECK:**
- [ ] Got an answer
- [ ] confidence > 70
- [ ] citations array has entries
- [ ] Retrieved correct document
- [ ] latency_ms < 5000

---

### Step 12: List Documents

```powershell
Invoke-WebRequest -Uri "http://localhost:8001/documents" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "documents": [
    {
      "id": 1,
      "title": "Company Policy",
      "filename": "test_policy.txt",
      "version": 1,
      "status": "ready",
      "created_at": "2026-01-26T02:25:00",
      "chunk_count": 1
    }
  ]
}
```

**✅ CHECK:**
- [ ] Shows uploaded document
- [ ] status is "ready"
- [ ] chunk_count > 0

**🎉 WEEK 2 COMPLETE IF ALL CHECKS PASSED**

---

## WEEK 3 VERIFICATION: DRIFT DETECTION (10 minutes)

### Step 13: Check Telemetry Service (Week 3)

```powershell
# Get dashboard stats
Invoke-WebRequest -Uri "http://localhost:8003/dashboard/stats" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "total_queries": 1,
  "avg_confidence": 88.5,
  "avg_latency_ms": 1850,
  "total_documents": 1,
  "confidence_change": 0
}
```

**✅ CHECK:**
- [ ] total_queries > 0
- [ ] avg_confidence > 0
- [ ] total_documents > 0

---

### Step 14: Check Drift Status

```powershell
Invoke-WebRequest -Uri "http://localhost:8003/dashboard/drift-status" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "data_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "No action needed"
  },
  "retrieval_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "Monitoring"
  },
  "performance_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "Stable"
  }
}
```

**✅ CHECK:**
- [ ] Shows all 3 drift types
- [ ] All show "no_drift" (initially)

---

### Step 15: Test Drift Detection - Trigger Manual Detection

```powershell
# Manually trigger drift detection
Invoke-WebRequest -Uri "http://localhost:8004/detect" `
  -Method Post `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "status": "detection_complete",
  "timestamp": "2026-01-26T02:30:00"
}
```

**✅ CHECK:**
- [ ] Returns success
- [ ] No errors

---

### Step 16: Verify Drift Detector Logs

```powershell
docker-compose logs drift_detector --tail=50
```

**Expected Output:**

```
✅ Drift Detector Service initialized - Running every 5 minutes
✅ Drift detection completed at 2026-01-26 02:30:00
```

**✅ CHECK:**
- [ ] Service initialized
- [ ] Running periodic detection
- [ ] No errors in logs

**🎉 WEEK 3 COMPLETE IF ALL CHECKS PASSED**

---

## WEEK 4 VERIFICATION: AUTO-CONTROLLER (15 minutes)

### Step 17: Check Controller Service

```powershell
Invoke-WebRequest -Uri "http://localhost:8005/health" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "status": "healthy",
  "service": "controller",
  "timestamp": "2026-01-26T02:35:00"
}
```

**✅ CHECK:**
- [ ] Returns healthy

---

### Step 18: Get Current System Configuration

```powershell
Invoke-WebRequest -Uri "http://localhost:8005/config" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "config": [
    {
      "config_key": "rag_params",
      "config_value": {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "top_k": 3,
        "confidence_threshold": 0.6,
        "similarity_threshold": 0.5
      },
      "updated_at": "2026-01-26T02:30:00"
    }
  ]
}
```

**✅ CHECK:**
- [ ] Shows rag_params
- [ ] top_k = 3 (default)
- [ ] All parameters present

---

### Step 19: Check Controller Action History

```powershell
Invoke-WebRequest -Uri "http://localhost:8005/actions/history" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected (initially empty):**

```json
{
  "actions": []
}
```

**✅ CHECK:**
- [ ] Returns array (empty is OK initially)

---

### Step 20: Test Auto-Controller - Simulate Drift

Upload a second version of the policy (changed content):

```powershell
# Create modified version
echo "Company Vacation Policy 2026: Employees now receive 20 days of paid vacation annually. Sick leave increased to 12 days per year. Full remote work allowed." > policy_v2.txt

# Upload it
$response = Invoke-WebRequest -Uri "http://localhost:8001/upload" `
  -Method Post `
  -Form @{
    file = Get-Item -Path "policy_v2.txt"
    title = "Company Policy"
  } -ErrorAction SilentlyContinue

$response.Content | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "success": true,
  "document_id": 2,
  "version": 2,
  ...
}
```

---

### Step 21: Make Queries to Generate Data

```powershell
# Ask same question multiple times
$query1 = @{ question = "How many vacation days?" } | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8002/query" -Method Post -ContentType "application/json" -Body $query1 -ErrorAction SilentlyContinue | Out-Null

# Wait 5 seconds
Start-Sleep -Seconds 5

$query2 = @{ question = "What is the sick leave policy?" } | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8002/query" -Method Post -ContentType "application/json" -Body $query2 -ErrorAction SilentlyContinue | Out-Null

Start-Sleep -Seconds 5

$query3 = @{ question = "Can employees work remotely?" } | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8002/query" -Method Post -ContentType "application/json" -Body $query3 -ErrorAction SilentlyContinue | Out-Null
```

---

### Step 22: Trigger Drift Detection

```powershell
Invoke-WebRequest -Uri "http://localhost:8004/detect" -Method Post -ErrorAction SilentlyContinue | Out-Null

# Wait 30 seconds for controller to respond
Start-Sleep -Seconds 30
```

---

### Step 23: Check if Controller Took Action

```powershell
Invoke-WebRequest -Uri "http://localhost:8005/actions/history" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected (if drift detected):**

```json
{
  "actions": [
    {
      "id": 1,
      "drift_event_id": 1,
      "action_type": "increase_top_k",
      "status": "success",
      "improvement_percent": 12.5,
      "before_metric": 78.2,
      "after_metric": 87.9,
      "created_at": "2026-01-26T02:40:00"
    }
  ]
}
```

**✅ CHECK:**
- [ ] Actions array has entries (if drift occurred)
- [ ] Shows action_type
- [ ] Shows improvement_percent
- [ ] status is "success"

*Note: If no drift detected yet, that's OK. System needs more data.*

---

### Step 24: Verify Controller Logs

```powershell
docker-compose logs controller --tail=50
```

**Expected:**

```
✅ Controller Service initialized
🔍 Starting drift event monitoring...
🚨 New drift event detected: retrieval_drift (medium)
🎯 Decided action: increase_top_k
📈 Increased top-k from 3 to 5
📊 Result: 78.2% → 87.9% (+12.5%)
✅ Logged action 1: increase_top_k - success - 12.5% improvement
```

**✅ CHECK:**
- [ ] Monitoring started
- [ ] No fatal errors
- [ ] If drift occurred, shows action taken

**🎉 WEEK 4 COMPLETE IF ALL CHECKS PASSED**

---

## WEEK 5 VERIFICATION: DOCKER COMPOSE + TESTING (10 minutes)

### Step 25: Verify All Dockerfiles Exist

```powershell
# Check each Dockerfile
Get-Item D:\Project\backend\services\upload\Dockerfile
Get-Item D:\Project\backend\services\query\Dockerfile
Get-Item D:\Project\backend\services\telemetry\Dockerfile
Get-Item D:\Project\backend\services\drift_detector\Dockerfile
Get-Item D:\Project\backend\services\controller\Dockerfile
Get-Item D:\Project\backend\services\evaluation\Dockerfile
```

**✅ CHECK:**
- [ ] All 6 Dockerfiles exist
- [ ] No "file not found" errors

---

### Step 26: Verify docker-compose.yml

```powershell
# View docker-compose.yml
Get-Content D:\Project\backend\docker-compose.yml | Select-String "services:" -Context 0,3
```

**Expected:** Shows services section with all 9 services

**✅ CHECK:**
- [ ] docker-compose.yml exists
- [ ] Contains all 9 services (postgres, qdrant, redis, upload, query, telemetry, drift_detector, controller, evaluation)

---

### Step 27: Test Evaluation Service (Week 5)

```powershell
Invoke-WebRequest -Uri "http://localhost:8006/run-evaluation" `
  -Method Post `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "run_id": 1,
  "total_questions": 5,
  "avg_confidence": 82.3,
  "avg_latency_ms": 2100,
  "hit_rate": 80.0,
  "results": [...]
}
```

**✅ CHECK:**
- [ ] Returns run_id
- [ ] Shows avg_confidence
- [ ] hit_rate > 0

---

### Step 28: Get Evaluation History

```powershell
Invoke-WebRequest -Uri "http://localhost:8006/eval-history" `
  -ErrorAction SilentlyContinue | ConvertFrom-Json | Format-List
```

**Expected:**

```json
{
  "history": [
    {
      "id": 1,
      "total_questions": 5,
      "avg_confidence": 82.3,
      "avg_latency_ms": 2100,
      "hit_rate": 80.0,
      "created_at": "2026-01-26T02:45:00"
    }
  ]
}
```

**✅ CHECK:**
- [ ] Shows evaluation runs
- [ ] Metrics look reasonable

---

### Step 29: Resource Usage Check

```powershell
docker stats --no-stream
```

**Expected:**

```
CONTAINER           CPU %   MEM USAGE / LIMIT     MEM %
cognimend-upload    2.5%    150MB / 8GB          1.88%
cognimend-query     3.2%    180MB / 8GB          2.25%
cognimend-postgres  1.1%    50MB / 8GB           0.63%
cognimend-qdrant    2.8%    120MB / 8GB          1.50%
...
```

**✅ CHECK:**
- [ ] CPU < 10% per service (when idle)
- [ ] Memory < 500MB per service
- [ ] No services using excessive resources

---

### Step 30: Run Automated Test Script

```powershell
cd D:\Project\backend
powershell -NoProfile -ExecutionPolicy Bypass -File ".\test-docker-setup.ps1"
```

This runs all tests automatically (30 minutes).

**Expected:** All tests pass with green checkmarks

**✅ CHECK:**
- [ ] Pre-flight checks pass
- [ ] Build succeeds
- [ ] All services healthy
- [ ] Upload test passes
- [ ] Query test passes
- [ ] Dashboard test passes
- [ ] Drift detection works
- [ ] Controller responds
- [ ] Evaluation completes
- [ ] Performance acceptable

**🎉 WEEK 5 COMPLETE IF ALL CHECKS PASSED**

---

## FINAL VERIFICATION: ALL WEEKS (5 minutes)

### Step 31: Complete System Test

```powershell
# 1. Upload a new document
echo "Employee Handbook: Work hours are 9 AM to 5 PM. Dress code is business casual." > handbook.txt

$response = Invoke-WebRequest -Uri "http://localhost:8001/upload" `
  -Method Post `
  -Form @{
    file = Get-Item -Path "handbook.txt"
    title = "Employee Handbook"
  } -ErrorAction SilentlyContinue

Write-Host "Upload result:"
$response.Content | ConvertFrom-Json | Format-List

# 2. Query it
$query = @{ question = "What are the work hours?" } | ConvertTo-Json
$response = Invoke-WebRequest -Uri "http://localhost:8002/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body $query `
  -ErrorAction SilentlyContinue

Write-Host "`nQuery result:"
$response.Content | ConvertFrom-Json | Format-List

# 3. Check dashboard updated
$response = Invoke-WebRequest -Uri "http://localhost:8003/dashboard/stats" `
  -ErrorAction SilentlyContinue
Write-Host "`nDashboard stats:"
$response.Content | ConvertFrom-Json | Format-List

# 4. List all documents
$response = Invoke-WebRequest -Uri "http://localhost:8001/documents" `
  -ErrorAction SilentlyContinue
Write-Host "`nDocuments:"
$response.Content | ConvertFrom-Json | Format-List

# 5. Check drift status
$response = Invoke-WebRequest -Uri "http://localhost:8003/dashboard/drift-status" `
  -ErrorAction SilentlyContinue
Write-Host "`nDrift status:"
$response.Content | ConvertFrom-Json | Format-List
```

**✅ CHECK:**
- [ ] Upload succeeds
- [ ] Query returns correct answer
- [ ] Dashboard shows updated stats
- [ ] Documents list shows all uploads
- [ ] System is stable

---

### Step 32: View Complete System Logs

```powershell
docker-compose logs --tail=100
```

**✅ CHECK:**
- [ ] No ERROR messages
- [ ] Services communicating
- [ ] Database queries working
- [ ] No crashes

---

## 📊 COMPLETE VERIFICATION CHECKLIST

### Week 1: Frontend ✅
- [ ] Vercel deployment live
- [ ] Frontend code in D:\Project\frontend
- [ ] Can run locally with npm run dev

### Week 2: RAG Backend ✅
- [ ] Upload service works
- [ ] Query service works
- [ ] Postgres database operational
- [ ] Qdrant vector search operational
- [ ] Redis caching operational
- [ ] Documents can be uploaded
- [ ] Queries return answers with citations

### Week 3: Drift Detection ✅
- [ ] Telemetry service healthy
- [ ] Dashboard shows stats
- [ ] Drift detector running
- [ ] 3 drift types monitored
- [ ] Manual detection trigger works

### Week 4: Auto-Controller ✅
- [ ] Controller service healthy
- [ ] Monitoring drift events
- [ ] System configuration readable
- [ ] Can take autonomous actions
- [ ] Actions logged to database
- [ ] Evaluation service operational

### Week 5: Docker Compose + Testing ✅
- [ ] All 6 Dockerfiles created
- [ ] docker-compose.yml complete
- [ ] All services containerized
- [ ] One-command start works
- [ ] Health checks operational
- [ ] Automated test script created
- [ ] All tests documented
- [ ] Resource usage acceptable

---

## ✅ SUCCESS CRITERIA

Your system is **PRODUCTION-READY** if:

- [ ] All 9 containers running
- [ ] All 6 services healthy
- [ ] Upload → Query → Answer works
- [ ] Dashboard shows metrics
- [ ] Drift detection active
- [ ] Controller monitoring
- [ ] No errors in logs
- [ ] Resource usage < 2GB total
- [ ] API latency < 5 seconds
- [ ] Automated tests pass

---

## 🔧 TROUBLESHOOTING COMMON ISSUES

### Issue: Container keeps restarting

```powershell
docker-compose logs <service-name>
```

Look for errors, usually:
- Missing OPENAI_API_KEY
- Database connection failed
- Python syntax error

---

### Issue: Service returns 500 error

```powershell
docker-compose logs <service-name> --tail=100
```

Check for Python exceptions

---

### Issue: Can't connect to database

```powershell
docker exec -it cognimend-postgres psql -U postgres -d cognimend -c "\dt"
```

Should show tables

---

### Issue: Port already in use

```powershell
netstat -ano | findstr :8001
```

Kill process or change port in docker-compose.yml

---

## 📈 NEXT STEPS AFTER VERIFICATION

### If ALL checks passed ✅

```
→ Week 6: Kubernetes deployment (optional)
→ Week 7: Demo video + documentation
→ Deploy to cloud (AWS/GCP/Azure)
→ Add to resume/portfolio
```

### If some checks failed ❌

```
→ Share error logs
→ Debug specific service
→ Fix issues
→ Re-run verification
```

---

## ⚡ QUICK COMMAND REFERENCE

```powershell
# Start system
cd D:\Project\backend
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f

# Stop system
docker-compose down

# Clean everything
docker-compose down -v

# Run tests
powershell -NoProfile -ExecutionPolicy Bypass -File ".\test-docker-setup.ps1"

# Restart service
docker-compose restart <service-name>

# View specific service logs
docker-compose logs <service-name> --tail=50

# Enter container shell
docker exec -it <container-name> /bin/bash

# Check resource usage
docker stats --no-stream
```

---

## 📝 WHAT TO REPORT

After completing verification, tell me:

1. **Which step you reached**
2. **Any errors encountered**
3. **Screenshots of:**
   - `docker ps` output
   - Successful query response
   - Dashboard stats
   - Controller actions (if any)

Then we can:
- Fix any issues
- Move to Week 6 (Kubernetes)
- Create demo video
- Deploy to production

---

## 🚀 START VERIFICATION NOW

```powershell
# Open PowerShell
cd D:\Project\backend

# Begin from Step 2
docker --version
```

Work through each step systematically. Mark each ✅ as you complete it.

**Good luck! 🎯**

---

## 📞 NEED HELP?

If you get stuck:

1. **Check the logs**: `docker-compose logs <service>`
2. **Verify connectivity**: `docker exec <container> ping <service>`
3. **Check config**: `type .env` and verify OPENAI_API_KEY
4. **Restart services**: `docker-compose restart`
5. **Full reset**: `docker-compose down -v && docker-compose up -d`

Remember: The system is designed to be resilient. Services auto-restart on failure and data persists in Docker volumes.

**You've got this! 💪**
