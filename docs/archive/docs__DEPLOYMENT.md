# 🚀 Cognimend Deployment Guide

> Complete guide to deploying Cognimend in local, Kubernetes, and cloud environments

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Cloud Deployments](#cloud-deployments)
5. [Monitoring Setup](#monitoring-setup)
6. [CI/CD Setup](#cicd-setup)
7. [Production Checklist](#production-checklist)
8. [Troubleshooting](#troubleshooting)
9. [Rollback Procedures](#rollback-procedures)
10. [Upgrade Guide](#upgrade-guide)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 100+ GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Required Tools

| Tool | Version | Installation |
|------|---------|--------------|
| Docker | 24.0+ | [Install Docker](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.20+ | Included with Docker Desktop |
| kubectl | 1.28+ | [Install kubectl](https://kubernetes.io/docs/tasks/tools/) |
| Helm | 3.12+ | [Install Helm](https://helm.sh/docs/intro/install/) |
| Python | 3.11+ | [Install Python](https://www.python.org/downloads/) |
| Node.js | 18+ | [Install Node.js](https://nodejs.org/) |

### Access Requirements

- **OpenRouter API Key**: [Get one here](https://openrouter.ai/keys)
- **Docker Hub Account** (for image storage)
- **Cloud Provider Account** (for cloud deployments)

### Verify Installation

```bash
# Check Docker
docker --version
docker compose version

# Check Kubernetes tools
kubectl version --client
helm version

# Check development tools
python --version
node --version
```

---

## Local Development

### Docker Compose Setup

#### Step 1: Clone Repository

```bash
git clone https://github.com/cognimend/cognimend.git
cd cognimend
```

#### Step 2: Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit the configuration
notepad backend/.env  # Windows
# nano backend/.env   # Linux/Mac
```

**Required environment variables:**
```ini
# OpenRouter API (Required)
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_PRESET=balanced

# Database (defaults provided)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=cognimend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<redacted-secret>

# Vector Database
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Cache
REDIS_HOST=redis
REDIS_PORT=6379

# Security
CORS_ORIGINS=http://localhost:8080,http://localhost:5173
```

#### Step 3: Start Services

```bash
cd backend

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

**Expected output:**
```
NAME                    STATUS        PORTS
cognimend-postgres      Up (healthy)  0.0.0.0:5432->5432/tcp
cognimend-qdrant        Up (healthy)  0.0.0.0:6333-6334->6333-6334/tcp
cognimend-redis         Up (healthy)  0.0.0.0:6379->6379/tcp
cognimend-upload        Up (healthy)  0.0.0.0:8001->8001/tcp
cognimend-query         Up (healthy)  0.0.0.0:8002->8002/tcp
cognimend-telemetry     Up (healthy)  0.0.0.0:8003->8003/tcp
cognimend-drift         Up (healthy)  0.0.0.0:8004->8004/tcp
cognimend-controller    Up (healthy)  0.0.0.0:8005->8005/tcp
cognimend-evaluation    Up (healthy)  0.0.0.0:8006->8006/tcp
cognimend-prometheus    Up            0.0.0.0:9090->9090/tcp
cognimend-grafana       Up            0.0.0.0:3000->3000/tcp
cognimend-jaeger        Up            0.0.0.0:16686->16686/tcp
```

#### Step 4: Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Upload API | http://localhost:8001 | API Key |
| Query API | http://localhost:8002 | API Key |
| Telemetry | http://localhost:8003 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |
| Jaeger | http://localhost:16686 | - |

#### Step 5: Verify Health

```bash
# Check service health
curl http://localhost:8002/health

# Expected response
{
  "status": "healthy",
  "version": "2.0.0",
  "checks": {
    "database": "healthy",
    "qdrant": "healthy",
    "redis": "healthy"
  }
}
```

#### Step 6: Run Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Access frontend at: http://localhost:8080

#### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

---

## Kubernetes Deployment

### Minikube Setup (Local K8s)

#### Step 1: Start Minikube

```bash
# Start with adequate resources
minikube start --cpus=4 --memory=8192 --di<redacted-api-key>=50g

# Enable required addons
minikube addons enable ingress
minikube addons enable metrics-server
minikube addons enable dashboard

# Verify cluster
kubectl cluster-info
kubectl get nodes
```

#### Step 2: Create Namespace

```bash
kubectl create namespace cognimend
kubectl config set-context --current --namespace=cognimend
```

#### Step 3: Configure Secrets

```bash
# Create secrets from literals
kubectl create secret generic cognimend-secrets \
  --from-literal=OPENROUTER_API_KEY=<redacted-api-key> \
  --from-literal=POSTGRES_PASSWORD=your-secure-password \
  --from-literal=REDIS_PASSWORD=your-redis-password \
  -n cognimend

# Or create from file
cat > secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: cognimend-secrets
  namespace: cognimend
type: Opaque
stringData:
  OPENROUTER_API_KEY: <redacted-api-key>
  POSTGRES_PASSWORD: your-secure-password
  REDIS_PASSWORD: your-redis-password
EOF

kubectl apply -f secrets.yaml
```

#### Step 4: Deploy Infrastructure

```bash
# Deploy persistent volumes
kubectl apply -f k8s/postgres-pv.yaml -n cognimend
kubectl apply -f k8s/qdrant-pv.yaml -n cognimend

# Deploy databases
kubectl apply -f k8s/postgres-deployment.yaml -n cognimend
kubectl apply -f k8s/qdrant-deployment.yaml -n cognimend
kubectl apply -f k8s/redis-deployment.yaml -n cognimend

# Wait for databases
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s -n cognimend
kubectl wait --for=condition=ready pod -l app=qdrant --timeout=120s -n cognimend
kubectl wait --for=condition=ready pod -l app=redis --timeout=120s -n cognimend
```

#### Step 5: Deploy Services

```bash
# Deploy ConfigMap
kubectl apply -f k8s/configmap.yaml -n cognimend

# Deploy services
kubectl apply -f k8s/upload-deployment.yaml -n cognimend
kubectl apply -f k8s/query-deployment.yaml -n cognimend
kubectl apply -f k8s/telemetry-deployment.yaml -n cognimend
kubectl apply -f k8s/drift-detector-deployment.yaml -n cognimend
kubectl apply -f k8s/controller-deployment.yaml -n cognimend
kubectl apply -f k8s/evaluation-deployment.yaml -n cognimend

# Deploy autoscalers
kubectl apply -f k8s/query-hpa.yaml -n cognimend
kubectl apply -f k8s/upload-hpa.yaml -n cognimend

# Deploy network policies
kubectl apply -f k8s/network-policies.yaml -n cognimend

# Deploy pod disruption budgets
kubectl apply -f k8s/pod-disruption-budgets.yaml -n cognimend

# Deploy ingress
kubectl apply -f k8s/ingress.yaml -n cognimend
```

#### Step 6: Using Kustomize (Alternative)

```bash
# Deploy everything at once
kubectl apply -k k8s/ -n cognimend

# View what will be deployed
kubectl kustomize k8s/
```

#### Step 7: Verify Deployment

```bash
# Check all pods
kubectl get pods -n cognimend -w

# Expected output
NAME                                READY   STATUS    RESTARTS   AGE
postgres-0                          1/1     Running   0          5m
qdrant-0                           1/1     Running   0          5m
redis-0                            1/1     Running   0          5m
upload-service-xxx                 1/1     Running   0          3m
query-service-xxx                  1/1     Running   0          3m
telemetry-service-xxx              1/1     Running   0          3m
drift-detector-service-xxx         1/1     Running   0          3m
controller-service-xxx             1/1     Running   0          3m
evaluation-service-xxx             1/1     Running   0          3m

# Check services
kubectl get svc -n cognimend

# Check ingress
kubectl get ingress -n cognimend

# Check HPA
kubectl get hpa -n cognimend
```

#### Step 8: Access Services

**Option A: Port Forward**
```bash
# Forward query service
kubectl port-forward svc/query-service 8002:8002 -n cognimend

# Forward all services (use script)
./k8s/deploy.ps1 -Action port-forward
```

**Option B: Minikube Tunnel**
```bash
# Enable tunnel
minikube tunnel

# Get ingress IP
kubectl get ingress -n cognimend
```

**Option C: NodePort**
```bash
# Get minikube IP
minikube ip

# Access via NodePort
curl http://$(minikube ip):30002/health
```

---

## Cloud Deployments

### AWS EKS

#### Step 1: Create EKS Cluster

```bash
# Install eksctl
# Windows (Chocolatey)
choco install eksctl

# Create cluster
eksctl create cluster \
  --name cognimend-cluster \
  --version 1.28 \
  --region us-west-2 \
  --nodegroup-name standard-workers \
  --node-type t3.large \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# Verify
kubectl get nodes
```

#### Step 2: Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name cognimend-cluster

# Verify connection
kubectl cluster-info
```

#### Step 3: Install AWS Load Balancer Controller

```bash
# Add Helm repo
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=cognimend-cluster \
  --set serviceAccount.create=true
```

#### Step 4: Deploy Application

```bash
# Create namespace
kubectl create namespace cognimend

# Create secrets
kubectl create secret generic cognimend-secrets \
  --from-literal=OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  --from-literal=POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  -n cognimend

# Deploy with Kustomize
kubectl apply -k k8s/ -n cognimend

# Or use Helm (if available)
helm install cognimend ./charts/cognimend \
  --namespace cognimend \
  --values values-production.yaml
```

#### Step 5: Configure ALB Ingress

```yaml
# k8s/ingress-aws.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cognimend-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS-1-2-2017-01
spec:
  rules:
    - host: api.cognimend.com
      http:
        paths:
          - path: /upload
            pathType: Prefix
            backend:
              service:
                name: upload-service
                port:
                  number: 8001
          - path: /query
            pathType: Prefix
            backend:
              service:
                name: query-service
                port:
                  number: 8002
```

---

### GCP GKE

#### Step 1: Create GKE Cluster

```bash
# Set project
gcloud config set project your-project-id

# Create cluster
gcloud container clusters create cognimend-cluster \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type e2-standard-4 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10 \
  --enable-autorepair \
  --enable-autoupgrade

# Get credentials
gcloud container clusters get-credentials cognimend-cluster --zone us-central1-a
```

#### Step 2: Deploy

```bash
# Create namespace and deploy
kubectl create namespace cognimend
kubectl apply -k k8s/ -n cognimend
```

---

### Azure AKS

#### Step 1: Create AKS Cluster

```bash
# Create resource group
az group create --name cognimend-rg --location eastus

# Create cluster
az aks create \
  --resource-group cognimend-rg \
  --name cognimend-cluster \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group cognimend-rg --name cognimend-cluster
```

#### Step 2: Deploy

```bash
kubectl create namespace cognimend
kubectl apply -k k8s/ -n cognimend
```

---

## Monitoring Setup

### Install Prometheus Operator

```bash
# Add Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.retention=30d
```

### Apply ServiceMonitors

```bash
# Apply Cognimend ServiceMonitors
kubectl apply -f k8s/servicemonitor.yaml -n cognimend

# Verify
kubectl get servicemonitors -n cognimend
```

### Import Grafana Dashboards

#### Option A: Via UI
1. Access Grafana: `kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring`
2. Login with admin/admin
3. Go to Dashboards → Import
4. Upload `k8s/grafana-dashboard-rag.json`

#### Option B: Via ConfigMap
```bash
# Create dashboard ConfigMap
kubectl create configmap grafana-dashboard-rag \
  --from-file=dashboard.json=k8s/grafana-dashboard-rag.json \
  -n monitoring

# Label for auto-discovery
kubectl label configmap grafana-dashboard-rag grafana_dashboard=1 -n monitoring
```

### Configure Alerts

```bash
# Apply PrometheusRule
kubectl apply -f k8s/prometheus-alerts.yaml -n cognimend

# Verify alerts
kubectl get prometheusrules -n cognimend
```

### Setup Jaeger Tracing

```bash
# Install Jaeger Operator
kubectl create namespace observability
kubectl apply -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.51.0/jaeger-operator.yaml -n observability

# Create Jaeger instance
cat <<EOF | kubectl apply -f -
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: jaeger
  namespace: observability
spec:
  strategy: production
  storage:
    type: elasticsearch
EOF

# Access Jaeger UI
kubectl port-forward svc/jaeger-query 16686:16686 -n observability
```

---

## CI/CD Setup

### GitHub Repository Setup

#### Step 1: Fork/Create Repository

```bash
# Initialize git (if not already)
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-org/cognimend.git
git push -u origin main
```

#### Step 2: Configure Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token |
| `KUBE_CONFIG` | Base64 encoded kubeconfig |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications |
| `POSTGRES_PASSWORD` | Database password |

```bash
# Encode kubeconfig
cat ~/.kube/config | base64 -w 0
```

#### Step 3: Enable Workflows

```bash
# Workflows are in .github/workflows/
# - ci-cd.yaml: Main CI/CD pipeline
# - performance.yaml: Load testing
# - test.yaml: Comprehensive tests

# Push to trigger
git push origin main
```

### Manual Deployment

```bash
# Build images
docker build -t cognimend/upload:latest backend/services/upload
docker build -t cognimend/query:latest backend/services/query

# Push to registry
docker push cognimend/upload:latest
docker push cognimend/query:latest

# Deploy
kubectl apply -k k8s/ -n cognimend

# Restart deployments
kubectl rollout restart deployment -n cognimend
```

### Automated Deployment

The CI/CD pipeline automatically:
1. Runs tests on PR
2. Builds images on merge to main
3. Deploys to staging
4. Runs integration tests
5. Promotes to production (manual approval)

---

## Production Checklist

### Security Hardening

- [ ] **Secrets Management**
  ```bash
  # Use external secrets operator
  kubectl apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/main/deploy/crds/bundle.yaml
  ```

- [ ] **Network Policies Applied**
  ```bash
  kubectl get networkpolicies -n cognimend
  # Should show policies for each service
  ```

- [ ] **Pod Security Standards**
  ```bash
  kubectl label namespace cognimend pod-security.kubernetes.io/enforce=restricted
  ```

- [ ] **TLS Enabled**
  ```bash
  # Install cert-manager
  kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
  
  # Create ClusterIssuer for Let's Encrypt
  kubectl apply -f - <<EOF
  apiVersion: cert-manager.io/v1
  kind: ClusterIssuer
  metadata:
    name: letsencrypt-prod
  spec:
    acme:
      server: https://acme-v02.api.letsencrypt.org/directory
      email: your-email@domain.com
      privateKeySecretRef:
        name: letsencrypt-prod
      solvers:
        - http01:
            ingress:
              class: nginx
  EOF
  ```

### Resource Configuration

- [ ] **Resource Limits Set**
  ```yaml
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  ```

- [ ] **HPA Configured**
  ```bash
  kubectl get hpa -n cognimend
  ```

- [ ] **PDB Configured**
  ```bash
  kubectl get pdb -n cognimend
  ```

### Backup Strategy

- [ ] **Database Backups**
  ```bash
  # PostgreSQL backup CronJob
  kubectl apply -f - <<EOF
  apiVersion: batch/v1
  kind: CronJob
  metadata:
    name: postgres-backup
    namespace: cognimend
  spec:
    schedule: "0 2 * * *"
    jobTemplate:
      spec:
        template:
          spec:
            containers:
            - name: backup
              image: postgres:15-alpine
              command:
              - /bin/sh
              - -c
              - pg_dump -h postgres -U postgres cognimend | gzip > /backup/backup-$(date +%Y%m%d).sql.gz
              volumeMounts:
              - name: backup
                mountPath: /backup
            volumes:
            - name: backup
              persistentVolumeClaim:
                claimName: backup-pvc
            restartPolicy: OnFailure
  EOF
  ```

- [ ] **Qdrant Snapshots**
  ```bash
  # Create snapshot
  curl -X POST http://localhost:6333/collections/documents/snapshots
  ```

### Health Checks

- [ ] **Liveness Probes**
- [ ] **Readiness Probes**
- [ ] **Startup Probes**

### Monitoring Alerts

- [ ] **Alert Rules Configured**
  ```bash
  kubectl get prometheusrules -n cognimend
  ```

- [ ] **Alert Receivers Configured** (Slack, PagerDuty, etc.)

---

## Troubleshooting

### Common Issues

#### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n cognimend

# Check logs
kubectl logs <pod-name> -n cognimend --previous

# Common fixes
# 1. Image pull issues
kubectl get events -n cognimend | grep -i pull

# 2. Resource constraints
kubectl top nodes
kubectl top pods -n cognimend

# 3. ConfigMap/Secret missing
kubectl get configmaps,secrets -n cognimend
```

#### Database Connection Issues

```bash
# Test PostgreSQL connectivity
kubectl run psql-test --rm -it --image=postgres:15-alpine -n cognimend -- \
  psql -h postgres -U postgres -d cognimend -c "SELECT 1"

# Check PostgreSQL logs
kubectl logs postgres-0 -n cognimend
```

#### Service Discovery Issues

```bash
# Check service endpoints
kubectl get endpoints -n cognimend

# DNS resolution test
kubectl run dns-test --rm -it --image=busybox -n cognimend -- \
  nslookup query-service.cognimend.svc.cluster.local
```

#### High Memory Usage

```bash
# Check memory usage
kubectl top pods -n cognimend --sort-by=memory

# Force garbage collection (Redis)
kubectl exec -it redis-0 -n cognimend -- redis-cli MEMORY PURGE

# Check for memory leaks
kubectl logs <pod-name> -n cognimend | grep -i memory
```

### Debugging Commands

```bash
# Get all resources in namespace
kubectl get all -n cognimend

# Describe all pods
kubectl describe pods -n cognimend

# Get pod YAML
kubectl get pod <pod-name> -n cognimend -o yaml

# Execute into pod
kubectl exec -it <pod-name> -n cognimend -- /bin/sh

# Port forward for debugging
kubectl port-forward <pod-name> 8080:8080 -n cognimend

# View recent events
kubectl get events -n cognimend --sort-by='.lastTimestamp' | tail -20
```

### Log Collection

```bash
# Collect all logs
mkdir logs
for pod in $(kubectl get pods -n cognimend -o jsonpath='{.items[*].metadata.name}'); do
  kubectl logs $pod -n cognimend > logs/$pod.log 2>&1
done

# Use stern for multi-pod logs
stern -n cognimend ".*" --since 1h > logs/all-services.log
```

### Performance Tuning

```bash
# Check resource utilization
kubectl top pods -n cognimend

# Increase replicas for high load
kubectl scale deployment query-service --replicas=5 -n cognimend

# Adjust HPA thresholds
kubectl edit hpa query-hpa -n cognimend
```

---

## Rollback Procedures

### Manual Rollback

```bash
# View rollout history
kubectl rollout history deployment/query-service -n cognimend

# Rollback to previous version
kubectl rollout undo deployment/query-service -n cognimend

# Rollback to specific revision
kubectl rollout undo deployment/query-service --to-revision=2 -n cognimend

# Verify rollback
kubectl rollout status deployment/query-service -n cognimend
```

### Automated Rollback

The CI/CD pipeline includes automatic rollback:

```yaml
# From .github/workflows/ci-cd.yaml
- name: Deploy with rollback
  run: |
    kubectl apply -k k8s/ -n cognimend
    if ! kubectl rollout status deployment/query-service -n cognimend --timeout=5m; then
      echo "Deployment failed, rolling back..."
      kubectl rollout undo deployment/query-service -n cognimend
      exit 1
    fi
```

### Database Rollback

```bash
# List backups
ls /backup/

# Restore PostgreSQL
kubectl exec -it postgres-0 -n cognimend -- \
  psql -U postgres -d cognimend < /backup/backup-20240131.sql

# Restore Qdrant from snapshot
curl -X PUT http://localhost:6333/collections/documents/snapshots/recover \
  -H "Content-Type: application/json" \
  -d '{"location": "/snapshots/snapshot-20240131"}'
```

---

## Upgrade Guide

### Version Compatibility

| From Version | To Version | Notes |
|--------------|------------|-------|
| 1.x | 2.0 | Database migration required |
| 2.0 | 2.1 | Backwards compatible |

### Migration Steps

#### Upgrade from 1.x to 2.0

```bash
# 1. Backup databases
kubectl exec -it postgres-0 -n cognimend -- pg_dump -U postgres cognimend > backup.sql

# 2. Scale down services
kubectl scale deployment --all --replicas=0 -n cognimend

# 3. Run migrations
kubectl apply -f migrations/v2-migration.yaml -n cognimend
kubectl wait --for=condition=complete job/v2-migration -n cognimend

# 4. Update images
kubectl set image deployment/query-service query=cognimend/query:2.0.0 -n cognimend
kubectl set image deployment/upload-service upload=cognimend/upload:2.0.0 -n cognimend

# 5. Scale up
kubectl scale deployment --all --replicas=1 -n cognimend

# 6. Verify
kubectl rollout status deployment --all -n cognimend
```

### Zero-Downtime Upgrades

```yaml
# Deployment strategy
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

```bash
# Perform rolling update
kubectl set image deployment/query-service query=cognimend/query:2.1.0 -n cognimend

# Monitor rollout
kubectl rollout status deployment/query-service -n cognimend

# Pause if issues detected
kubectl rollout pause deployment/query-service -n cognimend

# Resume
kubectl rollout resume deployment/query-service -n cognimend
```

---

## Quick Reference

### Useful Commands

```bash
# Deploy everything
kubectl apply -k k8s/ -n cognimend

# Check status
kubectl get all -n cognimend

# View logs
kubectl logs -f deployment/query-service -n cognimend

# Port forward
kubectl port-forward svc/query-service 8002:8002 -n cognimend

# Restart all
kubectl rollout restart deployment -n cognimend

# Scale service
kubectl scale deployment query-service --replicas=5 -n cognimend

# Delete everything
kubectl delete -k k8s/ -n cognimend
```

### Environment-Specific Commands

```bash
# Development
docker compose up -d

# Staging
kubectl apply -k k8s/overlays/staging -n cognimend-staging

# Production
kubectl apply -k k8s/overlays/production -n cognimend-production
```

---

**Need help?** Open an issue on [GitHub](https://github.com/cognimend/cognimend/issues) or contact support@cognimend.dev
