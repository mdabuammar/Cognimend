# 🚀 WEEK 5 DEPLOYMENT COMPLETE

## What You Now Have

A complete, production-ready autonomous RAG system deployed with Docker Compose.

### Single Command Startup
```bash
cd D:\Project\backend
docker-compose up -d
```

### All Services (9 Containers)
```
Infrastructure:
  ✅ PostgreSQL (5432)
  ✅ Qdrant Vector DB (6333)
  ✅ Redis Cache (6379)

Application Services:
  ✅ Upload Service (8001)
  ✅ Query Service (8002)
  ✅ Telemetry/Dashboard (8003)
  ✅ Drift Detector (8004)
  ✅ Auto-Controller (8005)
  ✅ Evaluation Service (8006)
```

---

## Your Complete Autonomous RAG System

### Week 1: Frontend
- React/TypeScript UI on Vercel
- Real-time dashboard
- Document upload interface

### Week 2: RAG Backend
- **Upload Service** - PDFs → chunks → embeddings → vector DB
- **Query Service** - Questions → retrieval → LLM → answers

### Week 3: Drift Detection
- **Telemetry Service** - Metrics & trends
- **Drift Detector** - 3 types of drift (data, retrieval, performance)
- Database monitoring every 5 minutes

### Week 4: Auto-Healing
- **Controller Service** - Auto-responds to drift
- **Evaluation Service** - Validates improvements
- Re-indexes, increases top-k, updates prompts automatically

### Week 5: Docker Orchestration (COMPLETE)
- **docker-compose.yml** - Orchestrates all 9 services
- **Dockerfiles** - Each service containerized
- **Helper scripts** - One-command startup/shutdown
- **Health checks** - Auto-restart on failure

---

## File Structure

```
D:\Project\backend\
├── docker-compose.yml          ← Main orchestration file
├── .env                        ← Your secrets (OPENAI_API_KEY)
├── .dockerignore              ← Exclude from builds
├── Makefile                   ← Development commands
├── start.sh / start.bat       ← One-command startup
├── stop.sh                    ← Clean shutdown
├── cleanup.sh                 ← Full reset
├── DOCKER_WEEK5.md           ← Complete documentation
│
└── services/
    ├── upload/        (Dockerfile + main.py + requirements.txt)
    ├── query/         (Dockerfile + main.py + requirements.txt)
    ├── telemetry/     (Dockerfile + main.py + requirements.txt)
    ├── drift_detector/(Dockerfile + main.py + requirements.txt)
    ├── controller/    (Dockerfile + main.py + requirements.txt)
    └── evaluation/    (Dockerfile + main.py + requirements.txt)
```

---

## Quick Start (3 Steps)

### 1. Edit .env
```bash
cd D:\Project\backend
```
Update `.env` with your OpenAI API key:
```
OPENAI_API_KEY=<your-openrouter-api-key>
```

### 2. Start System
**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
./start.sh
```

**Manual:**
```bash
docker-compose up -d
```

### 3. Wait 30 seconds, then test
```bash
# Check dashboard stats
curl http://localhost:8003/dashboard/stats

# Make a query
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the vacation policy?"}'

# Check action history
curl http://localhost:8005/actions/history

# Run evaluation
curl -X POST http://localhost:8006/run-evaluation
```

---

## Key Features

### 🏗️ Automatic Service Orchestration
- Correct startup order (dependencies)
- Health checks (30-second intervals)
- Auto-restart on failure
- Isolated network (cognimend-network)

### 📊 Complete Monitoring
- Service health endpoints
- Database connectivity checks
- Automatic logging
- Performance metrics

### 🔄 Self-Healing System
When drift detected:
1. **Drift Detector** → alerts
2. **Controller** → decides action
3. **Executes** → re-index / increase top-k / update prompts
4. **Evaluates** → measures improvement
5. **Logs** → records % improvement

### 📈 Dashboard Access
```
http://localhost:8003/dashboard/stats
http://localhost:8003/dashboard/drift-status
http://localhost:8003/dashboard/confidence-trend
http://localhost:8003/dashboard/query-volume
```

---

## Common Commands

### Start/Stop
```bash
# Start
docker-compose up -d

# Stop (keeps data)
docker-compose down

# Stop and delete all data
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f controller

# Last 100 lines
docker-compose logs --tail=100 drift_detector
```

### Using Makefile
```bash
make up              # Start all services
make down            # Stop all services
make logs            # View logs
make health          # Check service health
make clean           # Remove all data
make test            # Test query endpoint
```

### Check Status
```bash
docker-compose ps
```

---

## Environment Variables

Only ONE is required:
```bash
OPENAI_API_KEY=<your-openrouter-api-key>
```

Others have defaults:
```bash
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<redacted-secret>
```

---

## Testing the Full System

### Scenario: Document Upload → Drift → Auto-Fix

```bash
# 1. Upload a document
curl -X POST http://localhost:8001/upload \
  -F "file=@policy_v1.pdf" \
  -F "title=Company Policy"

# 2. Run some queries
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the vacation policy?"}'

# 3. Check dashboard
curl http://localhost:8003/dashboard/stats

# 4. Upload updated document (simulates drift)
curl -X POST http://localhost:8001/upload \
  -F "file=@policy_v2.pdf" \
  -F "title=Company Policy"

# 5. Trigger drift detection
curl -X POST http://localhost:8004/detect

# 6. Watch controller auto-respond
# (Check logs: docker-compose logs -f controller)

# 7. Check action history
curl http://localhost:8005/actions/history

# 8. Run evaluation
curl -X POST http://localhost:8006/run-evaluation

# 9. View improvement
curl http://localhost:8006/eval-history
```

---

## Troubleshooting

### Services won't start
```bash
# View logs
docker-compose logs

# Rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database won't connect
```bash
# Wait longer
sleep 30
docker-compose logs postgres

# Restart postgres
docker-compose restart postgres
```

### Port already in use
Edit `docker-compose.yml` and change ports (e.g., 8001:8001 → 8011:8001)

### Out of disk space
```bash
docker system prune -f
docker volume prune -f
```

---

## What's Different from Week 4

| Feature | Week 4 | Week 5 |
|---------|--------|--------|
| Startup | 7 terminal windows | 1 command |
| Service Order | Manual | Automatic (dependencies) |
| Failures | Manual restart | Auto-restart |
| Health Checks | Manual | Automatic (30s) |
| Networking | localhost | Internal container network |
| Deployment | Local only | Portable to any machine |
| Logging | 7 different terminals | Unified docker-compose logs |

---

## Production Checklist

✅ **Dockerfiles** - Each service containerized  
✅ **Docker Compose** - Complete orchestration  
✅ **Health Checks** - Automatic monitoring  
✅ **Service Dependencies** - Correct startup order  
✅ **Environment Config** - .env file support  
✅ **Auto-Restart** - Resilient to failures  
✅ **Networking** - Isolated, secure  
✅ **Volumes** - Data persistence  
✅ **Helper Scripts** - Easy operations  
✅ **Documentation** - Complete guides  

---

## Next Steps

### Week 6: Kubernetes
Scale to Kubernetes for multi-machine deployment.

### Production Deployment
1. Copy to server: `scp -r backend/ user@server:/app/`
2. Set `.env` with production secrets
3. Run: `docker-compose up -d`
4. Monitor: `docker-compose logs -f`

### Monitoring & Observability
- Add Prometheus for metrics
- Add Grafana for dashboards
- Add ELK for logging

### CI/CD Pipeline
- GitHub Actions for auto-build
- Automatic deployment on push
- Automated testing & validation

---

## Summary

You now have a **production-ready, fully autonomous RAG system** that:

✅ Detects quality degradation (drift)  
✅ Automatically fixes itself (controller)  
✅ Validates improvements (evaluation)  
✅ Deploys in one command (docker-compose)  
✅ Scales across machines (Kubernetes-ready)  
✅ Runs without intervention  

**Everything is containerized, orchestrated, and ready to deploy.**

---

## Start Now

```bash
cd D:\Project\backend
docker-compose up -d
```

**Your system is running! 🎉**
