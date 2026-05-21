# Quick Testing Guide

## TL;DR - Run Everything at Once

### Windows (PowerShell)
```powershell
cd D:\Project\backend
.\test-docker-setup.ps1
```

### Linux/Mac (Bash)
```bash
cd ~/Project/backend
chmod +x test-docker-setup.sh
./test-docker-setup.sh
```

---

## Testing Steps

### 1️⃣ Pre-Flight (2 min)
```powershell
docker --version
docker-compose --version
type .env
```

### 2️⃣ Build (5-10 min)
```powershell
docker-compose build
```

### 3️⃣ Start (2 min)
```powershell
docker-compose up -d
Start-Sleep -Seconds 30
```

### 4️⃣ Check Status (1 min)
```powershell
docker ps
```

**Expected: 9 containers all showing "Up" status**

### 5️⃣ Health Check (1 min)
```powershell
@(8001, 8002, 8003, 8004, 8005, 8006) | ForEach-Object {
    curl "http://localhost:$_/health"
}
```

**Expected: All return `"status": "healthy"`**

### 6️⃣ Upload Document (1 min)
```powershell
"Company Vacation Policy: 15 days paid vacation, 10 days sick leave." | Out-File test_policy.txt

curl -X POST http://localhost:8001/upload `
  -F "file=@test_policy.txt" `
  -F "title=Vacation Policy"
```

**Expected: `"success": true`**

### 7️⃣ Query Document (1 min)
```powershell
curl -X POST http://localhost:8002/query `
  -H "Content-Type: application/json" `
  -d '{"question": "How many vacation days?"}'
```

**Expected: Returns answer with confidence score**

### 8️⃣ Check Dashboard (1 min)
```powershell
curl http://localhost:8003/dashboard/stats
curl http://localhost:8003/dashboard/drift-status
```

---

## Advanced Testing

### Test Drift Detection
```powershell
# Upload v1
"Leave Policy: 15 days vacation" | Out-File policy_v1.txt
curl -X POST http://localhost:8001/upload -F "file=@policy_v1.txt" -F "title=Policy"

# Query baseline
curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d '{"question": "vacation days?"}'

# Upload v2 (changed)
"Leave Policy: 20 days vacation (updated)" | Out-File policy_v2.txt
curl -X POST http://localhost:8001/upload -F "file=@policy_v2.txt" -F "title=Policy"

# Trigger detection
curl -X POST http://localhost:8004/detect

# Check response
Start-Sleep -Seconds 5
curl http://localhost:8005/actions/history
```

---

## View Logs

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f controller

# Last 50 lines
docker-compose logs --tail=50 query
```

---

## Troubleshooting

### Services not starting?
```powershell
docker-compose logs upload
docker-compose logs postgres
```

### Can't connect to database?
```powershell
docker-compose restart postgres
Start-Sleep -Seconds 10
docker-compose up -d
```

### Port already in use?
```powershell
netstat -ano | findstr :8001
```

### Need to restart?
```powershell
docker-compose restart
```

### Need to reset everything?
```powershell
docker-compose down -v
docker-compose up -d
```

---

## Success Criteria ✅

- [ ] All 9 containers running
- [ ] All 6 services return "healthy"
- [ ] Upload works
- [ ] Query returns answers
- [ ] Dashboard shows stats
- [ ] Drift detection works
- [ ] Controller responds to drift
- [ ] No errors in logs

---

## Performance Metrics

```powershell
docker stats --no-stream
```

**Good:**
- CPU < 10% per container (idle)
- Memory < 500MB per service
- Postgres < 100MB

**Bad:**
- CPU > 50% constantly
- Memory > 2GB per service
- Services restarting frequently

---

## Stop System

```powershell
# Keep data
docker-compose down

# Delete all data
docker-compose down -v
```

---

## Full Automated Test (Windows)

```powershell
cd D:\Project\backend
.\test-docker-setup.ps1 -AdvancedDrift
```

Options:
- `-SkipBuild` - Skip docker-compose build
- `-SkipStart` - Skip starting services
- `-SkipTests` - Skip functional tests
- `-AdvancedDrift` - Include drift detection test

---

## Full Automated Test (Linux/Mac)

```bash
cd ~/Project/backend
./test-docker-setup.sh --drift
```

Options:
- `--skip-build` - Skip docker-compose build
- `--skip-start` - Skip starting services
- `--skip-tests` - Skip functional tests
- `--drift` - Include drift detection test

---

## Next Steps

✅ System working? Great!

→ Review [DOCKER_WEEK5.md](DOCKER_WEEK5.md) for detailed documentation

→ Check [Makefile](Makefile) for helpful commands

→ Ready for Week 6: Kubernetes deployment

---

## Quick Command Reference

```powershell
# Status
docker ps                          # List containers
docker-compose ps                  # Docker Compose status
docker stats --no-stream          # Resource usage

# Logs
docker-compose logs -f             # All logs
docker-compose logs -f service     # Specific service

# Management
docker-compose up -d              # Start
docker-compose down               # Stop (keep data)
docker-compose down -v            # Stop (delete data)
docker-compose restart            # Restart
docker-compose build              # Rebuild images

# Testing
curl http://localhost:PORT/health # Health check
docker-compose exec upload bash   # Shell access
```

---

**Ready to deploy to production? Week 6: Kubernetes! 🚀**
