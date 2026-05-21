# 🚀 DriftGuard Production Deployment Guide

## Scalability Infrastructure for 10K+ Concurrent Users

This document provides complete instructions for deploying DriftGuard's production-grade infrastructure.

---

## 📊 Capacity Overview

| Tier | Concurrent Users | Queries/Day | DB Connections | API Replicas |
|------|------------------|-------------|----------------|--------------|
| Development | 50 | 50,000 | 2-10 | 1-2 |
| Small | 500 | 250,000 | 5-25 | 2-5 |
| Medium | 2,000 | 1,000,000 | 10-50 | 3-10 |
| **Large** | **10,000** | **5,000,000** | **20-100** | **5-25** |
| Enterprise | 50,000 | 25,000,000 | 50-200 | 10-50 |

---

## 🏗️ Architecture Components

### Infrastructure (Kubernetes)

```
infrastructure/kubernetes/
├── namespace.yaml          # Namespace + ResourceQuota + LimitRange
├── api-deployment.yaml     # API Service + HPA (3-50 replicas)
├── frontend-deployment.yaml # Frontend + HPA (2-20 replicas)
├── ingress.yaml            # NGINX Ingress + SSL + Rate Limiting
├── redis-cluster.yaml      # Redis Cluster (6 nodes)
├── qdrant-cluster.yaml     # Qdrant Vector DB (3 nodes)
├── prometheus.yaml         # Prometheus + Alerting (12 rules)
└── grafana.yaml            # Grafana Dashboards
```

### Backend Scaling Modules

```
backend/services/shared/
├── database_scaling.py     # Connection pooling, Read replicas, Sharding
├── vector_db_scaling.py    # Qdrant clustering, Load balancing
├── cache_service.py        # L1/L2 caching, Redis cluster
├── rate_limiting.py        # Distributed rate limiting, Circuit breakers
├── metrics.py              # Prometheus metrics, Instrumentation
└── backpressure.py         # Load shedding, Bulkheads, AIMD
```

### Database Migration

```
database/migrations/
└── 003_scaling_optimizations.sql  # Partitioning, Indexes, Materialized views
```

---

## 🚀 Quick Start Deployment

### Prerequisites

1. **Kubernetes Cluster** (1.28+)
   - Minimum: 3 nodes, 8 CPU cores, 32GB RAM each
   - Recommended: 5+ nodes for production
   
2. **kubectl** configured with cluster access

3. **Container Registry** access for your images

### Step 1: Configure Secrets

```bash
# Create secrets file (don't commit to git!)
kubectl create secret generic driftguard-secrets \
  --from-literal=database_url="postgresql://user:pass@host:5432/db" \
  --from-literal=openrouter_api_key="<redacted-api-key>" \
  --from-literal=redis_password="your-redis-password" \
  --from-literal=grafana_password="your-grafana-password" \
  -n driftguard
```

### Step 2: Deploy Infrastructure

```powershell
# Using the deployment script (Windows)
cd infrastructure
.\deploy.ps1 -Environment prod

# Or manually with kubectl
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/redis-cluster.yaml
kubectl apply -f kubernetes/qdrant-cluster.yaml
kubectl apply -f kubernetes/prometheus.yaml
kubectl apply -f kubernetes/grafana.yaml
kubectl apply -f kubernetes/api-deployment.yaml
kubectl apply -f kubernetes/frontend-deployment.yaml
kubectl apply -f kubernetes/ingress.yaml
```

### Step 3: Run Database Migration

```bash
kubectl exec -it deployment/driftguard-api -n driftguard -- \
  python -c "from database.migrations import run_migrations; run_migrations()"

# Or connect directly to PostgreSQL
psql $DATABASE_URL -f database/migrations/003_scaling_optimizations.sql
```

### Step 4: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n driftguard

# Check HPA is working
kubectl get hpa -n driftguard

# Check services
kubectl get svc -n driftguard

# Check ingress
kubectl get ingress -n driftguard
```

---

## 📈 Monitoring & Observability

### Access Dashboards

```bash
# Grafana (port 3000)
kubectl port-forward svc/grafana 3000:3000 -n driftguard
# Open: http://localhost:3000 (admin / <your-password>)

# Prometheus (port 9090)
kubectl port-forward svc/prometheus 9090:9090 -n driftguard
# Open: http://localhost:9090
```

### Key Metrics to Monitor

| Metric | Warning | Critical | Description |
|--------|---------|----------|-------------|
| `http_request_duration_seconds` (P95) | > 1s | > 3s | API latency |
| `error_rate` | > 1% | > 5% | Error percentage |
| `cache_hit_rate` | < 70% | < 50% | Cache effectiveness |
| `db_connections_active` | > 80% | > 95% | Connection pool usage |
| `circuit_breaker_state` | half-open | open | Service health |
| `rate_limit_hits_total` | Increasing | Spiking | Rate limit pressure |

### Alerting

Prometheus is configured with 12 alerting rules:

- **HighErrorRate**: >5% errors for 5 minutes
- **HighLatency**: P95 >3s for 5 minutes  
- **PodCrashLooping**: Pod restarting >3 times in 10 minutes
- **HighMemoryUsage**: >85% memory for 5 minutes
- **HighCPUUsage**: >85% CPU for 5 minutes
- **CacheHitRateLow**: <50% cache hits for 10 minutes
- **CircuitBreakerOpen**: Any circuit breaker open
- **DatabaseConnectionsHigh**: >90% pool utilization
- **QdrantClusterUnhealthy**: Node failures
- **RedisClusterUnhealthy**: Cluster issues
- **OpenRouterQuotaLow**: <10% quota remaining
- **HighRateLimitHits**: Excessive rate limiting

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis cluster URL | `redis://redis-cluster:6379` |
| `QDRANT_URL` | Qdrant cluster URL | `http://qdrant:6333` |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `SCALE_TIER` | Capacity tier (development/small/medium/large/enterprise) | `medium` |
| `CACHE_TTL_SECONDS` | Cache TTL | `3600` |
| `RATE_LIMIT_TIER` | Rate limit tier (free/pro/enterprise) | `pro` |

### Scaling Configuration

```python
# backend/services/shared/database_scaling.py
from shared.database_scaling import ScaleTier, ScalableDatabase

# Configure for your tier
db = ScalableDatabase(
    tier=ScaleTier.LARGE,  # For 10K users
    master_url=os.getenv("DATABASE_URL"),
    replica_urls=[
        os.getenv("DATABASE_REPLICA_1"),
        os.getenv("DATABASE_REPLICA_2"),
    ]
)
```

### Rate Limiting Configuration

```python
# Tier-based limits
RATE_LIMITS = {
    "free": {"requests_per_minute": 50, "daily_queries": 1000},
    "pro": {"requests_per_minute": 200, "daily_queries": 10000},
    "enterprise": {"requests_per_minute": 1000, "daily_queries": 100000},
}
```

---

## 🧪 Load Testing

### Run Load Tests

```powershell
# Smoke test (10 users, 30 seconds)
.\load_test.ps1 -TestType smoke -BaseUrl "https://api.yourapp.com"

# Load test (100 users, 60 seconds)
.\load_test.ps1 -TestType load -BaseUrl "https://api.yourapp.com"

# Stress test (500 users, 120 seconds)
.\load_test.ps1 -TestType stress -BaseUrl "https://api.yourapp.com"

# Spike test (1000 users, 30 seconds)
.\load_test.ps1 -TestType spike -BaseUrl "https://api.yourapp.com"
```

### Expected Results for 10K Users

| Metric | Target | Acceptable |
|--------|--------|------------|
| Throughput | > 5,000 req/s | > 2,000 req/s |
| P95 Latency | < 200ms | < 500ms |
| P99 Latency | < 500ms | < 1000ms |
| Error Rate | < 0.1% | < 1% |
| Success Rate | > 99.9% | > 99% |

---

## 🔄 Scaling Operations

### Manual Scaling

```bash
# Scale API pods
kubectl scale deployment driftguard-api --replicas=20 -n driftguard

# Check HPA status
kubectl get hpa driftguard-api-hpa -n driftguard -o yaml
```

### Automatic Scaling (HPA)

The HPA is configured to scale based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)
- Requests per second (target: 1000/pod)

```yaml
# Current HPA configuration
minReplicas: 3
maxReplicas: 50
metrics:
  - cpu: 70%
  - memory: 80%
  - requests: 1000/pod
```

### Database Scaling

```python
# Add read replica
db.add_replica("postgresql://user:pass@replica-host:5432/db")

# Enable sharding (for enterprise scale)
db.enable_sharding(
    shard_count=4,
    shard_key="organization_id"
)
```

---

## 🛡️ High Availability

### Component Redundancy

| Component | Replicas | Anti-Affinity | PDB |
|-----------|----------|---------------|-----|
| API Service | 3-50 | Zone-aware | minAvailable: 2 |
| Frontend | 2-20 | Zone-aware | minAvailable: 1 |
| Redis | 6 (3 master + 3 replica) | Node-aware | N/A |
| Qdrant | 3 | Node-aware | N/A |
| PostgreSQL | 1 master + 2 replicas | Zone-aware | External |

### Disaster Recovery

1. **Database**: Automated backups every 6 hours, PITR enabled
2. **Redis**: AOF persistence, cluster failover
3. **Qdrant**: Collection snapshots, replication factor 2
4. **Secrets**: External secret manager (Vault/AWS Secrets)

---

## 📋 Troubleshooting

### Common Issues

#### High Latency
```bash
# Check database connections
kubectl exec -it deployment/driftguard-api -- python -c \
  "from shared.metrics import get_db_stats; print(get_db_stats())"

# Check cache hit rate
kubectl exec -it deployment/driftguard-api -- python -c \
  "from shared.cache_service import cache; print(cache.stats())"
```

#### Circuit Breaker Open
```bash
# Check circuit breaker state
kubectl logs deployment/driftguard-api | grep "circuit_breaker"

# Reset circuit breaker (if needed)
kubectl exec -it deployment/driftguard-api -- python -c \
  "from shared.rate_limiting import circuit_breaker; circuit_breaker.reset()"
```

#### Rate Limiting Issues
```bash
# Check rate limit hits
kubectl exec -it deployment/driftguard-api -- python -c \
  "from shared.rate_limiting import rate_limiter; print(rate_limiter.get_stats())"
```

---

## 📚 Files Reference

### Infrastructure Files
- [namespace.yaml](infrastructure/kubernetes/namespace.yaml) - Kubernetes namespace
- [api-deployment.yaml](infrastructure/kubernetes/api-deployment.yaml) - API deployment
- [frontend-deployment.yaml](infrastructure/kubernetes/frontend-deployment.yaml) - Frontend
- [ingress.yaml](infrastructure/kubernetes/ingress.yaml) - Ingress configuration
- [redis-cluster.yaml](infrastructure/kubernetes/redis-cluster.yaml) - Redis cluster
- [qdrant-cluster.yaml](infrastructure/kubernetes/qdrant-cluster.yaml) - Qdrant cluster
- [prometheus.yaml](infrastructure/kubernetes/prometheus.yaml) - Monitoring
- [grafana.yaml](infrastructure/kubernetes/grafana.yaml) - Dashboards

### Backend Modules
- [database_scaling.py](backend/services/shared/database_scaling.py) - Database scaling
- [vector_db_scaling.py](backend/services/shared/vector_db_scaling.py) - Vector DB scaling
- [cache_service.py](backend/services/shared/cache_service.py) - Caching layer
- [rate_limiting.py](backend/services/shared/rate_limiting.py) - Rate limiting
- [metrics.py](backend/services/shared/metrics.py) - Prometheus metrics
- [backpressure.py](backend/services/shared/backpressure.py) - Backpressure control

### Database
- [003_scaling_optimizations.sql](database/migrations/003_scaling_optimizations.sql) - Migration

---

## ✅ Deployment Checklist

- [ ] Kubernetes cluster provisioned (3+ nodes)
- [ ] Container images built and pushed
- [ ] Secrets configured in cluster
- [ ] Namespace created with resource quotas
- [ ] Redis cluster deployed (6 pods running)
- [ ] Qdrant cluster deployed (3 pods running)
- [ ] PostgreSQL configured with replicas
- [ ] Database migration executed
- [ ] API service deployed with HPA
- [ ] Frontend deployed with HPA
- [ ] Ingress configured with SSL
- [ ] Prometheus collecting metrics
- [ ] Grafana dashboards accessible
- [ ] Alerting rules configured
- [ ] Load test passed (100+ concurrent users)
- [ ] DNS configured for production domain
- [ ] SSL certificates valid

---

**🎉 Your DriftGuard system is now ready for 10,000+ concurrent users!**
