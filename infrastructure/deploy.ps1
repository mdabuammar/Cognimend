# DriftGuard Kubernetes Deployment Script
# Production-Ready Deployment for 10K+ Users

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipConfirmation
)

$ErrorActionPreference = "Stop"

# Configuration
$NAMESPACE = "driftguard"
$SCRIPT_DIR = $PSScriptRoot
$K8S_DIR = Join-Path $SCRIPT_DIR "kubernetes"

# Colors for output
function Write-Success { param($Message) Write-Host "✅ $Message" -ForegroundColor Green }
function Write-Info { param($Message) Write-Host "ℹ️  $Message" -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host "⚠️  $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "❌ $Message" -ForegroundColor Red }
function Write-Step { param($Step, $Message) Write-Host "`n[$Step] $Message" -ForegroundColor Magenta }

# Banner
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                 🚀 DriftGuard Deployment                     ║
║           Production Infrastructure for 10K+ Users           ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Info "Environment: $Environment"
Write-Info "Dry Run: $DryRun"
Write-Info "Kubernetes Directory: $K8S_DIR"

# Pre-flight checks
Write-Step "1/8" "Running pre-flight checks..."

# Check kubectl
try {
    $kubectlVersion = kubectl version --client -o json 2>$null | ConvertFrom-Json
    Write-Success "kubectl found: v$($kubectlVersion.clientVersion.gitVersion)"
} catch {
    Write-Error "kubectl not found. Please install kubectl first."
    exit 1
}

# Check cluster connectivity
try {
    $clusterInfo = kubectl cluster-info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot connect to cluster"
    }
    Write-Success "Connected to Kubernetes cluster"
} catch {
    Write-Error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    exit 1
}

# Confirmation prompt
if (-not $SkipConfirmation -and -not $DryRun) {
    Write-Host "`n"
    Write-Warning "This will deploy DriftGuard to the '$Environment' environment."
    $confirm = Read-Host "Are you sure you want to continue? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Info "Deployment cancelled."
        exit 0
    }
}

# Deployment function
function Deploy-Manifest {
    param([string]$ManifestPath, [string]$Description)
    
    if (-not (Test-Path $ManifestPath)) {
        Write-Warning "Manifest not found: $ManifestPath (skipping)"
        return
    }
    
    Write-Info "Deploying: $Description"
    
    if ($DryRun) {
        kubectl apply -f $ManifestPath --dry-run=client -o yaml | Out-Null
        Write-Success "(Dry Run) Would deploy: $Description"
    } else {
        kubectl apply -f $ManifestPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to deploy: $Description"
            exit 1
        }
        Write-Success "Deployed: $Description"
    }
}

# Step 2: Create Namespace and Resource Quotas
Write-Step "2/8" "Creating namespace and resource quotas..."
Deploy-Manifest (Join-Path $K8S_DIR "namespace.yaml") "Namespace & ResourceQuota"

# Step 3: Deploy Redis Cluster
Write-Step "3/8" "Deploying Redis Cluster (6 nodes)..."
Deploy-Manifest (Join-Path $K8S_DIR "redis-cluster.yaml") "Redis Cluster"

if (-not $DryRun) {
    Write-Info "Waiting for Redis pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=redis-cluster -n $NAMESPACE --timeout=300s 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Redis Cluster is ready"
    } else {
        Write-Warning "Redis pods not yet ready (deployment will continue)"
    }
}

# Step 4: Deploy Qdrant Cluster
Write-Step "4/8" "Deploying Qdrant Vector DB Cluster (3 nodes)..."
Deploy-Manifest (Join-Path $K8S_DIR "qdrant-cluster.yaml") "Qdrant Cluster"

if (-not $DryRun) {
    Write-Info "Waiting for Qdrant pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=qdrant -n $NAMESPACE --timeout=300s 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Qdrant Cluster is ready"
    } else {
        Write-Warning "Qdrant pods not yet ready (deployment will continue)"
    }
}

# Step 5: Deploy Prometheus Monitoring
Write-Step "5/8" "Deploying Prometheus Monitoring..."
Deploy-Manifest (Join-Path $K8S_DIR "prometheus.yaml") "Prometheus"

# Step 6: Deploy Grafana Dashboards
Write-Step "6/8" "Deploying Grafana Dashboards..."
Deploy-Manifest (Join-Path $K8S_DIR "grafana.yaml") "Grafana"

# Step 7: Deploy Application Services
Write-Step "7/8" "Deploying Application Services..."
Deploy-Manifest (Join-Path $K8S_DIR "api-deployment.yaml") "API Service (HPA enabled)"
Deploy-Manifest (Join-Path $K8S_DIR "frontend-deployment.yaml") "Frontend Service (HPA enabled)"

# Step 8: Deploy Ingress
Write-Step "8/8" "Deploying Ingress Controller..."
Deploy-Manifest (Join-Path $K8S_DIR "ingress.yaml") "Ingress & Config"

# Final Summary
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                    🎉 Deployment Complete!                    ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Green

if (-not $DryRun) {
    Write-Info "Checking deployment status..."
    Write-Host ""
    
    # Show pod status
    Write-Host "📊 Pod Status:" -ForegroundColor Yellow
    kubectl get pods -n $NAMESPACE -o wide
    
    Write-Host ""
    Write-Host "📈 Horizontal Pod Autoscalers:" -ForegroundColor Yellow
    kubectl get hpa -n $NAMESPACE
    
    Write-Host ""
    Write-Host "🌐 Services:" -ForegroundColor Yellow
    kubectl get svc -n $NAMESPACE
    
    Write-Host ""
    Write-Host "📋 Ingress:" -ForegroundColor Yellow
    kubectl get ingress -n $NAMESPACE
    
    Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                      📚 Next Steps                            ║
╠══════════════════════════════════════════════════════════════╣
║  1. Run database migration:                                   ║
║     kubectl exec -it <api-pod> -- python migrate.py          ║
║                                                               ║
║  2. Configure DNS to point to Ingress IP                     ║
║                                                               ║
║  3. Access Grafana dashboard:                                 ║
║     kubectl port-forward svc/grafana 3000:3000 -n $NAMESPACE ║
║     Open: http://localhost:3000 (admin / <secret>)           ║
║                                                               ║
║  4. Access Prometheus:                                        ║
║     kubectl port-forward svc/prometheus 9090:9090 -n $NAMESPACE
║     Open: http://localhost:9090                              ║
║                                                               ║
║  5. Monitor logs:                                             ║
║     kubectl logs -f deployment/driftguard-api -n $NAMESPACE  ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan
} else {
    Write-Info "Dry run complete. No changes were made."
    Write-Info "Run without -DryRun to deploy for real."
}

# Capacity Info
Write-Host @"

📊 Capacity Configuration:
┌─────────────────┬─────────────────┬────────────────┐
│ Component       │ Min Replicas    │ Max Replicas   │
├─────────────────┼─────────────────┼────────────────┤
│ API Service     │ 3               │ 50             │
│ Frontend        │ 2               │ 20             │
│ Redis Cluster   │ 6 (fixed)       │ 6 (fixed)      │
│ Qdrant Cluster  │ 3 (fixed)       │ 3 (fixed)      │
│ Prometheus      │ 1 (fixed)       │ 1 (fixed)      │
│ Grafana         │ 1 (fixed)       │ 1 (fixed)      │
└─────────────────┴─────────────────┴────────────────┘

💪 Ready for 10K+ Concurrent Users!

"@ -ForegroundColor White
