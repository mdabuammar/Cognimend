# ⚡ QUICK START - Run the Automated Test

## One Command to Test Everything

```powershell
cd D:\Project\backend
.\test-docker-setup.ps1
```

That's it! This single command will:

✅ Validate your setup  
✅ Build Docker images  
✅ Start all services  
✅ Run health checks  
✅ Test upload/query/dashboard  
✅ Simulate drift detection  
✅ Validate auto-healing  
✅ Check performance  
✅ Generate results  

---

## Step-by-Step Execution

### Step 1: Navigate to Backend (10 seconds)
```powershell
cd D:\Project\backend
```

You should see files like:
- docker-compose.yml
- .env
- test-docker-setup.ps1

### Step 2: Enable Script Execution (One-time only)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

This allows PowerShell to run local scripts.

### Step 3: Run the Test Script (30 minutes)
```powershell
.\test-docker-setup.ps1
```

Or with drift detection test:
```powershell
.\test-docker-setup.ps1 -AdvancedDrift
```

---

## What You'll See During Execution

### Phase 1: PRE-FLIGHT CHECK (30 seconds)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 1: PRE-FLIGHT CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ️  Checking Docker installation...
✅ Docker: Docker version 24.0.0, build abcdef1
✅ Docker Compose: Docker Compose version v2.20.0
✅ .env file found
✅ OPENAI_API_KEY configured
✅ services/upload/Dockerfile exists
✅ services/query/Dockerfile exists
... (all 6 Dockerfiles)
```

**Expected:** All checks pass with green ✅

### Phase 2: BUILD DOCKER IMAGES (5-10 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 2: BUILDING DOCKER IMAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ️  This may take 5-10 minutes...

[+] Building 234.5s (45/45) FINISHED
 => [upload internal] load build definition from Dockerfile
 => [upload stage-0 1/6] FROM python:3.11-slim
 => [upload stage-0 2/6] WORKDIR /app
 => [upload stage-0 3/6] RUN apt-get update && apt-get install
 ... (many lines of build output)

✅ Docker build completed successfully
```

**Expected:** BUILD output, then green ✅

**What's happening:** Downloading base Python images and installing dependencies

### Phase 3: START SERVICES (2 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 3: STARTING SERVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Docker Compose started

ℹ️  Waiting 30 seconds for services to stabilize...
```

**Expected:** See output, then wait counter reaches 30 seconds

### Phase 4: VERIFY CONTAINERS (1 minute)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 4: VERIFYING CONTAINERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ cognimend-postgres is running
✅ cognimend-qdrant is running
✅ cognimend-redis is running
✅ cognimend-upload is running
✅ cognimend-query is running
✅ cognimend-telemetry is running
✅ cognimend-drift-detector is running
✅ cognimend-controller is running
✅ cognimend-evaluation is running
```

**Expected:** All 9 containers show ✅ running

### Phase 5: HEALTH CHECK (2 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 5: HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Upload (8001): HEALTHY
✅ Query (8002): HEALTHY
✅ Telemetry (8003): HEALTHY
✅ Drift Detector (8004): HEALTHY
✅ Controller (8005): HEALTHY
✅ Evaluation (8006): HEALTHY
```

**Expected:** All 6 services show ✅ HEALTHY

### Phase 6: FUNCTIONAL TESTS (5-10 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 6: FUNCTIONAL TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ️  Creating test document...
✅ Test file created

ℹ️  Testing upload service...
✅ Upload successful (document_id: 1)

ℹ️  Testing query service...
✅ Query successful
   Answer: Employees get 15 days of paid vacation per year.
   Confidence: 85.3%

ℹ️  Testing dashboard...
✅ Dashboard stats retrieved
   Total queries: 1
   Avg confidence: 85.3%

ℹ️  Testing drift detection...
✅ Drift status retrieved
   Data drift: no_drift
   Retrieval drift: no_drift
   Performance drift: no_drift

ℹ️  Running evaluation suite...
✅ Evaluation completed (run_id: 1)
   Questions: 5
   Avg confidence: 78.5%
   Hit rate: 80.0%
```

**Expected:** All tests show ✅ successful

### Phase 7: ADVANCED DRIFT TEST (Optional - 5 minutes)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 7: ADVANCED DRIFT DETECTION TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ️  Uploading document v1...
✅ Document v1 uploaded

ℹ️  Getting baseline confidence...
   Baseline confidence: 88.2%

ℹ️  Uploading document v2 (simulating drift)...
✅ Document v2 uploaded

ℹ️  Triggering drift detection...
✅ Drift detection triggered

ℹ️  Checking drift status...
   Data drift: data_drift detected

ℹ️  Checking controller response...
✅ Controller took 1 action(s)
   Latest action: reindex_documents
   Improvement: 5.3%
```

**Expected:** Drift detected, controller responds, improvement shown

### Phase 8: COMPLETION
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TESTING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ All basic tests passed!

Next steps:
  1. Review logs: docker-compose logs -f
  2. Monitor system: docker stats --no-stream
  3. Stop system: docker-compose down
  4. Check documentation: DOCKER_WEEK5.md

✅ Your Docker Compose setup is working perfectly!
```

**Expected:** Summary with all ✅ and next steps

---

## Interpreting Results

### ✅ All Green = Perfect!
- All containers running
- All services healthy
- All tests passing
- System working perfectly

### ❌ Red Errors = Needs Fixing

**If you see ❌ errors:**

1. **Build failed:**
   ```powershell
   docker-compose logs
   ```
   Check for missing dependencies or network issues

2. **Container not running:**
   ```powershell
   docker-compose logs <service-name>
   docker-compose restart <service-name>
   ```

3. **Service unhealthy:**
   ```powershell
   docker-compose logs <service-name>
   ```
   Usually database connection or Python error

4. **Test failed:**
   ```powershell
   docker-compose logs -f
   # Look for error messages
   ```

---

## Common Questions During Testing

### "Why is the build taking so long?"
First build downloads base images (~2-3 GB). Subsequent builds are much faster.

### "Can I stop it and restart?"
Yes! You can press `Ctrl+C` anytime. Services stay running in Docker.
```powershell
# Resume testing
.\test-docker-setup.ps1 -SkipBuild -SkipStart
```

### "Is my internet being used?"
Yes, during build phase to download base images and packages.

### "Why does it pause for 30 seconds?"
Waiting for databases (PostgreSQL, Qdrant) to initialize.

### "Can I run it on my laptop?"
Yes, but needs:
- 8 GB RAM minimum
- 30 GB free disk space
- Decent internet connection
- Docker Desktop running

---

## After Testing Completes

### Success ✅
```powershell
# Your system is ready!
# View logs
docker-compose logs -f

# Access services
curl http://localhost:8003/dashboard/stats

# Stop when done
docker-compose down
```

### Want to Keep It Running?
```powershell
# Services stay running in background
# You can close PowerShell and come back later

# Later, to check status
docker ps

# To view logs
docker-compose logs -f

# To stop
docker-compose down
```

---

## Advanced Options

### Run with drift detection test
```powershell
.\test-docker-setup.ps1 -AdvancedDrift
```

### Skip build (if already built)
```powershell
.\test-docker-setup.ps1 -SkipBuild
```

### Skip starting services
```powershell
.\test-docker-setup.ps1 -SkipStart
```

### Skip functional tests
```powershell
.\test-docker-setup.ps1 -SkipTests
```

### Combine options
```powershell
.\test-docker-setup.ps1 -SkipBuild -AdvancedDrift
```

---

## Exit Codes

```
0 = Success ✅
1 = Error ❌
```

### If you get exit code 1
```powershell
# View detailed error
docker-compose logs

# Check specific service
docker-compose logs upload

# See what went wrong
docker-compose ps
```

---

## Troubleshooting

### Script won't run
```powershell
# Enable script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then run
.\test-docker-setup.ps1
```

### Docker not found
```powershell
# Install Docker Desktop from https://www.docker.com

# Or verify it's in PATH
docker --version
```

### Out of disk space
```powershell
# Clean up Docker
docker system prune -f

# Remove all volumes
docker volume prune -f
```

### Need to reset everything
```powershell
# Stop and remove all data
docker-compose down -v

# Then run test again
.\test-docker-setup.ps1
```

---

## Performance Expectations

| Phase | Time | What Happens |
|-------|------|---|
| Pre-flight | 30 sec | Validation |
| Build | 5-10 min | Download images, install packages |
| Start | 2 min | Containers initialize |
| Health check | 2 min | Services become ready |
| Functional tests | 5-10 min | Upload, query, dashboard |
| Drift test | 5 min | Detection and response |
| **Total** | **~30 min** | **Full validation** |

---

## What Happens to Your System

### During Test
- Docker images built and stored locally
- 9 containers started
- Databases initialized with test data
- Services tested with real requests
- Drift detection simulated

### After Test
- All containers still running
- All data persisted in Docker volumes
- Can query system anytime
- Can view logs anytime
- Can stop with `docker-compose down`

---

## One More Time - The Command

```powershell
cd D:\Project\backend
.\test-docker-setup.ps1
```

That's literally all you need to do! ✨

The script handles everything else automatically.

---

## What's Next?

✅ Script completes successfully?
→ Everything works! 🎉

✅ Review results?
→ Check logs: `docker-compose logs -f`

✅ Deploy to production?
→ Copy to server and run: `docker-compose up -d`

✅ Scale to Kubernetes?
→ Week 6: Kubernetes deployment

✅ Need help?
→ Check [TESTING_GUIDE.md](TESTING_GUIDE.md)

---

**Ready? Let's go!**

```powershell
cd D:\Project\backend
.\test-docker-setup.ps1
```

Your entire autonomous RAG system will be tested and validated in 30 minutes! ⚡
