# Week 5: Complete Docker Compose Setup

## Overview

Week 5 packages your entire autonomous RAG system into a single production-ready Docker Compose orchestration.

**Before Week 5 (7 terminal windows):**
- Terminal 1: Docker infrastructure (postgres, qdrant, redis)
- Terminal 2-7: Individual Python services

**After Week 5 (single command):**
```bash
docker-compose up
```

Everything runs automatically with health checks, auto-restart, and service dependencies.

---

## What's Included

### 6 Dockerfiles (One per Service)
- `services/upload/Dockerfile`
- `services/query/Dockerfile`
- `services/telemetry/Dockerfile`
- `services/drift_detector/Dockerfile`
- `services/controller/Dockerfile`
- `services/evaluation/Dockerfile`

### Complete Docker Compose
- `docker-compose.yml` - Production-ready orchestration
- `.dockerignore` - Exclude unnecessary files from builds
- `.env` - Environment configuration template

### Helper Scripts
- `start.sh` / `start.bat` - One-command startup with health checks
- `stop.sh` - Clean shutdown
- `cleanup.sh` - Full reset (remove all data)
- `Makefile` - Development commands

---

## Quick Start

### 1. Edit .env File
```bash
cd D:\Project\backend
```

Open `.env` and add your OpenAI API key:
```bash
OPENAI_API_KEY=<your-openrouter-api-key>
```

### 2. Windows: Run start.bat
```bash
start.bat
```

Or Linux/Mac:
```bash
chmod +x start.sh
./start.sh
```

Or manually:
```bash
docker-compose up -d
```

### 3. Wait 30 seconds for services to be healthy

### 4. Test the system
```bash
# Check dashboard
curl http://localhost:8003/dashboard/stats

# Make a query
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test"}'
```

---

## Service Architecture

### Infrastructure (Always Running)
```
postgres:5432    → PostgreSQL database
qdrant:6333      → Vector store
redis:6379       → Cache (optional)
```

### Application Services (Start in Order)

```
upload:8001      → Depends on: postgres, qdrant
query:8002       → Depends on: postgres, qdrant
telemetry:8003   → Depends on: postgres
drift_detector:8004 → Depends on: postgres, qdrant
controller:8005  → Depends on: postgres, drift_detector
evaluation:8006  → Depends on: postgres, query
```

All services:
- Have health checks (every 30 seconds)
- Auto-restart on failure (unless-stopped)
- Run on isolated network (cognimend-network)

---

## Common Commands

### Using start.bat / start.sh
```bash
# Start everything
./start.sh              # Linux/Mac
start.bat              # Windows

# Stop everything
./stop.sh              # Linux/Mac
docker-compose down    # Windows
```

### Using Makefile
```bash
make build              # Build Docker images
make up                 # Start services
make down               # Stop services
make logs               # View live logs
make health             # Check service health
make clean              # Remove all data
make restart            # Restart services
make test               # Run test query
```

### Using Docker Compose Directly
```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f controller         # Specific service
docker-compose logs --tail=100 query      # Last 100 lines

# Check status
docker-compose ps

# Stop
docker-compose down                       # Keeps data
docker-compose down -v                    # Remove all data

# Rebuild (after code changes)
docker-compose build
docker-compose up -d
```

---

## Environment Variables

### Required
```bash
OPENAI_API_KEY=<your-openrouter-api-key>
```

### Database (with defaults)
```bash
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<redacted-secret>
```

### Qdrant (auto-configured in compose)
```bash
QDRANT_HOST=qdrant        # Use container name
QDRANT_PORT=6333
```

---

## Access Services

Once running:
```
Upload Service:      http://localhost:8001
Query Service:       http://localhost:8002
Telemetry/Dashboard: http://localhost:8003
Drift Detector:      http://localhost:8004
Controller:          http://localhost:8005
Evaluation:          http://localhost:8006
```

### Dashboard Endpoints
```bash
# Main stats
curl http://localhost:8003/dashboard/stats

# Drift status
curl http://localhost:8003/dashboard/drift-status

# Confidence trend (24h)
curl http://localhost:8003/dashboard/confidence-trend

# Query volume (24h)
curl http://localhost:8003/dashboard/query-volume
```

---

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs controller

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database connection errors
```bash
# Wait longer for postgres to start
sleep 30
docker-compose logs postgres

# Rebuild postgres
docker-compose down postgres
docker-compose up -d postgres
sleep 10
docker-compose up -d
```

### Out of memory
```bash
# Clean up Docker
docker system prune -f
docker volume prune -f
```

### Port conflicts
- Ports 8001-8006 needed for services
- Ports 5432, 6333, 6379 needed for databases
- Edit `docker-compose.yml` to change ports if needed

---

## Data Persistence

All data is stored in Docker volumes:
```
postgres_data    → PostgreSQL database
qdrant_data      → Vector embeddings
redis_data       → Cache data
```

### Backup
```bash
# Backup postgres
docker-compose exec postgres pg_dump -U postgres cognimend > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres cognimend < backup.sql
```

### Reset Everything
```bash
# THIS DELETES ALL DATA
docker-compose down -v

# Restart fresh
docker-compose up -d
```

---

## Production Deployment

### On Your Server

1. **Copy files to server:**
```bash
scp -r backend/ user@server:/app/
```

2. **Create .env with production keys:**
```bash
ssh user@server
cd /app/backend
nano .env
# Add OPENAI_API_KEY and other secrets
```

3. **Start system:**
```bash
docker-compose up -d
docker-compose logs -f
```

### Advanced Options

**Scale services** (docker-compose.yml):
```yaml
services:
  query:
    deploy:
      replicas: 3
```

**Add memory limits**:
```yaml
services:
  upload:
    deploy:
      resources:
        limits:
          memory: 2G
```

**Use external database**:
Change in `.env`:
```bash
POSTGRES_HOST=external-db.example.com
```

---

## Next Steps (Week 6+)

### Kubernetes Deployment
```bash
kubectl apply -f k8s-deployment.yaml
```

### Monitoring & Logging
- Add Prometheus for metrics
- Add ELK stack for logging
- Add Grafana for dashboards

### CI/CD Pipeline
- GitHub Actions for auto-build
- Automatic deployment on push
- Automated testing

---

## Support

### Check System Health
```bash
make health
```

### View All Logs
```bash
docker-compose logs
```

### Interactive Shell
```bash
# Access upload service
docker-compose exec upload /bin/bash

# Access database
docker-compose exec postgres psql -U postgres -d cognimend
```

### Reset to Clean State
```bash
./cleanup.sh
./start.sh
```

---

## Summary

✅ **6 Dockerfiles** - One per service  
✅ **Complete docker-compose.yml** - Production-ready orchestration  
✅ **Health checks** - Automatic monitoring  
✅ **Auto-restart** - Resilient to failures  
✅ **Service dependencies** - Correct startup order  
✅ **Helper scripts** - One-command start/stop  
✅ **Makefile** - Easy development workflow  
✅ **Production-ready** - Ready for deployment  

**Deploy your entire system with one command:**
```bash
docker-compose up
```
