# Docker Compose Testing Checklist

## Quick Reference Testing Steps

### Pre-Flight Check (2 min)
```powershell
# Verify Docker is installed and running
docker --version
docker-compose --version

# Check .env file exists
dir .env

# View .env content
type .env
```

### Build & Start (10 min)
```powershell
cd D:\Project\backend

# Build Docker images
docker-compose build

# Start all services
docker-compose up -d

# Wait 30 seconds for services to be ready
Start-Sleep -Seconds 30

# Check running containers
docker ps
```

### Health Check (2 min)
```powershell
# Test all services at once
@(8001, 8002, 8003, 8004, 8005, 8006) | ForEach-Object {
    Write-Host "Testing port $_..." -ForegroundColor Cyan
    try {
        $response = curl -s http://localhost:$_/health
        $response | ConvertFrom-Json | Select-Object service, status
    } catch {
        Write-Host "❌ Service on port $_ not responding" -ForegroundColor Red
    }
}
```

### End-to-End Functional Test (5 min)

**1. Create test file:**
```powershell
# Create test document
"Company Vacation Policy: Employees get 15 days of paid vacation per year. Sick leave is 10 days annually." | Out-File test_policy.txt -Encoding UTF8
```

**2. Upload document:**
```powershell
curl -X POST http://localhost:8001/upload `
  -F "file=@test_policy.txt" `
  -F "title=Vacation Policy"
```

Expected response:
```json
{
  "success": true,
  "document_id": 1,
  "chunks": 1,
  "status": "ready"
}
```

**3. Query the document:**
```powershell
curl -X POST http://localhost:8002/query `
  -H "Content-Type: application/json" `
  -d '{"question": "How many vacation days do employees get?"}'
```

Expected response:
```json
{
  "answer": "Employees get 15 days of paid vacation per year.",
  "confidence": 85.3,
  "latency_ms": 1850,
  "retrieved_count": 1
}
```

**4. Check dashboard:**
```powershell
curl http://localhost:8003/dashboard/stats
```

**5. Check drift status:**
```powershell
curl http://localhost:8003/dashboard/drift-status
```

**6. List documents:**
```powershell
curl http://localhost:8001/documents
```

**7. Run evaluation:**
```powershell
curl -X POST http://localhost:8006/run-evaluation
```

### View Logs

**All services:**
```powershell
docker-compose logs -f
# Press Ctrl+C to stop
```

**Specific service:**
```powershell
docker-compose logs -f upload
docker-compose logs -f query
docker-compose logs -f controller
docker-compose logs -f drift_detector
```

### Advanced: Drift Detection Test (10 min)

```powershell
# 1. Upload v1
"Leave Policy: 15 days vacation, 10 days sick leave." | Out-File policy_v1.txt -Encoding UTF8
curl -X POST http://localhost:8001/upload -F "file=@policy_v1.txt" -F "title=Leave Policy"

# 2. Query baseline
curl -X POST http://localhost:8002/query `
  -H "Content-Type: application/json" `
  -d '{"question": "How many vacation days?"}'

# 3. Upload v2 (changed content)
"Leave Policy: 20 days vacation, 12 days sick leave. Updated 2026." | Out-File policy_v2.txt -Encoding UTF8
curl -X POST http://localhost:8001/upload -F "file=@policy_v2.txt" -F "title=Leave Policy"

# 4. Trigger drift detection
curl -X POST http://localhost:8004/detect

# 5. Check drift status
curl http://localhost:8003/dashboard/drift-status

# 6. Wait and check controller actions
Start-Sleep -Seconds 30
curl http://localhost:8005/actions/history
```

### Performance Check

```powershell
# Check resource usage
docker stats --no-stream
```

Good metrics:
- CPU < 10% per container (idle)
- Memory < 500MB per service
- Postgres < 100MB

### Cleanup

```powershell
# Stop all services (keep data)
docker-compose down

# Stop and remove all data
docker-compose down -v

# Restart
docker-compose restart
```

---

## Testing Checklist

### Pre-Flight ✅
- [ ] Docker installed and running
- [ ] .env file exists with OPENAI_API_KEY
- [ ] All Dockerfiles in services/ directories

### Build ✅
- [ ] `docker-compose build` completes without errors
- [ ] All 6 images created successfully
- [ ] No build errors in output

### Start ✅
- [ ] `docker-compose up -d` succeeds
- [ ] All 9 containers running (docker ps shows all)
- [ ] No "Exited" status containers

### Health ✅
- [ ] Port 8001 /health responds with "healthy"
- [ ] Port 8002 /health responds with "healthy"
- [ ] Port 8003 /health responds with "healthy"
- [ ] Port 8004 /health responds with "healthy"
- [ ] Port 8005 /health responds with "healthy"
- [ ] Port 8006 /health responds with "healthy"

### Functionality ✅
- [ ] Upload document returns success with document_id
- [ ] Query returns answer with citations and confidence
- [ ] Dashboard /stats returns metrics
- [ ] Drift status shows "no_drift" for all types
- [ ] /documents endpoint returns uploaded document
- [ ] Evaluation /run-evaluation returns results

### Advanced ✅
- [ ] Drift detection endpoint /detect responds
- [ ] Drift detector logs show detection cycle
- [ ] Controller logs show monitoring active
- [ ] After drift, controller logs show action taken
- [ ] /actions/history shows logged actions

### Performance ✅
- [ ] CPU usage < 10% per service
- [ ] Memory usage reasonable (< 500MB per service)
- [ ] No constant container restarts
- [ ] All services stay running

---

## Troubleshooting Quick Reference

### Container keeps restarting
```powershell
docker-compose logs <service-name>
# Check for: Missing OPENAI_API_KEY, Python errors, DB connection issues
```

### Can't connect to database
```powershell
docker-compose logs postgres
docker-compose ps postgres
```

### Service returns 500 error
```powershell
docker-compose logs <service-name>
# Look for Python exception tracebacks
```

### Port already in use
```powershell
netstat -ano | findstr :8001
# Edit docker-compose.yml to change port mapping
```

### Qdrant connection failed
```powershell
curl http://localhost:6333/
docker-compose logs qdrant
```

---

## Success Criteria

✅ All 9 containers running
✅ All 6 services return "healthy"
✅ Can upload document
✅ Can query and get answer with citations
✅ Dashboard returns metrics
✅ No errors in logs
✅ Drift detection works
✅ Controller responds to drift
✅ Resource usage reasonable

**Your Docker Compose setup is production-ready!** 🎉
