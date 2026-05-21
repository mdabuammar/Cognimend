# Cognimend Kubernetes Deployment Guide

## Overview

This directory contains complete Kubernetes manifests for deploying the Cognimend RAG system with 6 microservices, 3 databases, and full production-grade configuration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Ingress (NGINX)                               │
│                    api.cognimend.example.com                             │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────────────┐
│                         Application Layer                                │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌──────────────┐ ┌────────────┐  │
│  │ Upload  │ │  Query  │ │ Telemetry │ │ Drift-Detect │ │ Controller │  │
│  │ (8001)  │ │ (8002)  │ │  (8003)   │ │   (8004)     │ │  (8005)    │  │
│  │ 2-6 rep │ │ 3-10rep │ │  1 rep    │ │   1 rep      │ │  1 rep     │  │
│  └────┬────┘ └────┬────┘ └─────┬─────┘ └──────┬───────┘ └─────┬──────┘  │
│       │          │            │              │               │          │
│  ┌────┴──────────┴────────────┴──────────────┴───────────────┴────┐     │
│  │                      Evaluation Service (8006)                  │     │
│  └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────────────┐
│                          Database Layer                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │   PostgreSQL    │  │     Qdrant      │  │      Redis      │          │
│  │   (5432)        │  │  (6333/6334)    │  │     (6379)      │          │
│  │   10Gi PVC      │  │   20Gi PVC      │  │    5Gi PVC      │          │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Kubernetes Cluster** (1.25+)
2. **kubectl** configured with cluster access
3. **NGINX Ingress Controller** installed
4. **cert-manager** for TLS (optional)
5. **Prometheus** for custom metrics HPA (optional)
6. **Storage Class** for PersistentVolumes

## Files Structure

```
k8s/
├── namespace.yaml              # Namespace definition
├── configmap.yaml              # Environment configuration
├── secrets.yaml                # Sensitive credentials (template)
├── postgres-pv.yaml            # PostgreSQL storage
├── postgres-deployment.yaml    # PostgreSQL deployment + service
├── qdrant-pv.yaml              # Qdrant storage
├── qdrant-deployment.yaml      # Qdrant deployment + service
├── redis-deployment.yaml       # Redis deployment + PVC + service
├── upload-deployment.yaml      # Upload service (2 replicas)
├── query-deployment.yaml       # Query service (3 replicas)
├── telemetry-deployment.yaml   # Telemetry service
├── drift-detector-deployment.yaml  # Drift detector service
├── controller-deployment.yaml  # Controller service
├── evaluation-deployment.yaml  # Evaluation service
├── ingress.yaml                # Ingress + RBAC
├── query-hpa.yaml              # Query autoscaling
├── upload-hpa.yaml             # Upload autoscaling
├── network-policies.yaml       # Zero-trust networking
├── pod-disruption-budgets.yaml # HA guarantees
├── kustomization.yaml          # Kustomize config
└── README.md                   # This file
```

## Quick Start

### 1. Configure Secrets

Before deploying, create the secrets file with actual values:

```bash
# Create secrets from template
cp secrets.yaml secrets-actual.yaml

# Edit with real values (never commit this file!)
# Replace placeholders with base64-encoded values:
# echo -n "your-password" | base64
```

Required secrets:
- `POSTGRES_PASSWORD`: PostgreSQL password
- `OPENROUTER_API_KEY`: OpenRouter API key
- `API_KEY`: Internal API authentication key
- `JWT_SECRET`: JWT signing secret
- `ENCRYPTION_KEY`: Data encryption key

### 2. Deploy with Kustomize

```bash
# Preview the deployment
kubectl kustomize k8s/

# Apply all resources
kubectl apply -k k8s/

# Or apply individually in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml  # Use your actual secrets file!
kubectl apply -f k8s/
```

### 3. Verify Deployment

```bash
# Check namespace
kubectl get all -n cognimend

# Check pods are running
kubectl get pods -n cognimend -w

# Check services
kubectl get svc -n cognimend

# Check ingress
kubectl get ingress -n cognimend

# Check HPAs
kubectl get hpa -n cognimend
```

## Configuration

### Environment Variables

All configuration is centralized in `configmap.yaml`. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL hostname | `postgresql` |
| `QDRANT_HOST` | Qdrant hostname | `qdrant` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_FILE_SIZE_MB` | Max upload size | `50` |
| `LLM_MODEL` | OpenRouter model | `meta-llama/llama-3.1-8b-instruct` |

### Resource Limits

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Upload | 200m | 500m | 256Mi | 512Mi |
| Query | 250m | 500m | 512Mi | 1Gi |
| Telemetry | 100m | 250m | 256Mi | 512Mi |
| Drift-Detector | 250m | 500m | 512Mi | 1Gi |
| Controller | 100m | 250m | 256Mi | 512Mi |
| Evaluation | 100m | 250m | 256Mi | 512Mi |
| PostgreSQL | 250m | 500m | 512Mi | 1Gi |
| Qdrant | 250m | 1 | 1Gi | 2Gi |
| Redis | 100m | 250m | 256Mi | 512Mi |

### Autoscaling

| Service | Min Replicas | Max Replicas | CPU Target | Memory Target |
|---------|--------------|--------------|------------|---------------|
| Query | 3 | 10 | 70% | 80% |
| Upload | 2 | 6 | 75% | 85% |

## Security Features

### Network Policies
- **Default deny**: All ingress/egress blocked by default
- **Explicit allow**: Each service has specific ingress/egress rules
- **Database isolation**: Databases only accessible from app pods
- **External access**: Only HTTPS (443) to external APIs

### Pod Security
- **Non-root execution**: All containers run as UID 1000
- **Read-only filesystem**: Containers have read-only root
- **Dropped capabilities**: All Linux capabilities dropped
- **No privilege escalation**: Prevented at container level

### Ingress Security
- **TLS termination**: HTTPS with cert-manager
- **Rate limiting**: 100 req/s, 1000 req/min
- **Security headers**: HSTS, CSP, X-Frame-Options
- **CORS**: Restricted to specific origins

## Monitoring

All services expose Prometheus metrics on port 9090:

```bash
# Check metrics endpoints
kubectl port-forward svc/query 9090:9090 -n cognimend
curl http://localhost:9090/metrics
```

### Prometheus Scrape Config

Services are annotated for auto-discovery:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9090"
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n cognimend

# Check logs
kubectl logs <pod-name> -n cognimend

# Check resource constraints
kubectl top pods -n cognimend
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
kubectl exec -it postgresql-0 -n cognimend -- pg_isready

# Check Qdrant health
kubectl exec -it qdrant-0 -n cognimend -- curl localhost:6333/healthz

# Check Redis
kubectl exec -it redis-0 -n cognimend -- redis-cli ping
```

### Network Policy Issues

```bash
# Test connectivity between pods
kubectl exec -it upload-xxx -n cognimend -- nc -zv postgresql 5432

# Check network policies
kubectl get networkpolicy -n cognimend
kubectl describe networkpolicy <policy-name> -n cognimend
```

## Production Checklist

- [ ] Replace `secrets.yaml` with actual secrets (Sealed Secrets or External Secrets)
- [ ] Update `ingress.yaml` with real domain name
- [ ] Configure TLS certificates (cert-manager)
- [ ] Set up external monitoring (Prometheus/Grafana)
- [ ] Configure backup for PostgreSQL and Qdrant
- [ ] Set up log aggregation (Loki/ELK)
- [ ] Configure alerting rules
- [ ] Test disaster recovery procedures
- [ ] Review and adjust resource limits based on load testing
- [ ] Enable Pod Security Standards/Policies

## Customization with Kustomize

Create overlays for different environments:

```
k8s/
├── base/           # Move current files here
├── overlays/
│   ├── development/
│   │   └── kustomization.yaml
│   ├── staging/
│   │   └── kustomization.yaml
│   └── production/
│       └── kustomization.yaml
```

Example production overlay:
```yaml
# overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
images:
  - name: cognimend/query-service
    newTag: v2.0.0
patchesStrategicMerge:
  - increase-replicas.yaml
```
