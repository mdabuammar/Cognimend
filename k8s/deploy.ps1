# =============================================================================
# Cognimend Kubernetes Deployment Script (PowerShell)
# =============================================================================

param(
    [Parameter()]
    [ValidateSet("apply", "delete", "status", "logs", "restart")]
    [string]$Action = "status",
    
    [Parameter()]
    [string]$Namespace = "cognimend",
    
    [Parameter()]
    [string]$Service = ""
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Test-Kubectl {
    try {
        kubectl version --client | Out-Null
        return $true
    }
    catch {
        Write-Host "ERROR: kubectl is not installed or not in PATH" -ForegroundColor Red
        return $false
    }
}

function Get-DeploymentOrder {
    return @(
        "namespace.yaml",
        "configmap.yaml",
        "secrets.yaml",
        "postgres-pv.yaml",
        "qdrant-pv.yaml",
        "postgres-deployment.yaml",
        "qdrant-deployment.yaml",
        "redis-deployment.yaml",
        "upload-deployment.yaml",
        "query-deployment.yaml",
        "telemetry-deployment.yaml",
        "drift-detector-deployment.yaml",
        "controller-deployment.yaml",
        "evaluation-deployment.yaml",
        "ingress.yaml",
        "query-hpa.yaml",
        "upload-hpa.yaml",
        "network-policies.yaml",
        "pod-disruption-budgets.yaml"
    )
}

function Deploy-Resources {
    Write-Header "Deploying Cognimend to Kubernetes"
    
    $k8sPath = Split-Path -Parent $PSCommandPath
    $files = Get-DeploymentOrder
    
    foreach ($file in $files) {
        $filePath = Join-Path $k8sPath $file
        if (Test-Path $filePath) {
            Write-Host "Applying: $file" -ForegroundColor Green
            kubectl apply -f $filePath
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR applying $file" -ForegroundColor Red
                exit 1
            }
        }
        else {
            Write-Host "SKIP: $file not found" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`nDeployment complete!" -ForegroundColor Green
    Write-Host "Waiting for pods to be ready..."
    Start-Sleep -Seconds 5
    
    Get-Status
}

function Remove-Resources {
    Write-Header "Removing Cognimend from Kubernetes"
    
    $confirm = Read-Host "Are you sure you want to delete all resources? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Aborted." -ForegroundColor Yellow
        return
    }
    
    Write-Host "Deleting namespace $Namespace and all resources..." -ForegroundColor Yellow
    kubectl delete namespace $Namespace --grace-period=30
    
    # Delete PVs (they're not namespaced)
    Write-Host "Deleting PersistentVolumes..." -ForegroundColor Yellow
    kubectl delete pv postgres-pv qdrant-pv --ignore-not-found
    
    Write-Host "Cleanup complete!" -ForegroundColor Green
}

function Get-Status {
    Write-Header "Cognimend Cluster Status"
    
    Write-Host "=== Namespace ===" -ForegroundColor Cyan
    kubectl get namespace $Namespace 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Namespace '$Namespace' does not exist" -ForegroundColor Yellow
        return
    }
    
    Write-Host "`n=== Pods ===" -ForegroundColor Cyan
    kubectl get pods -n $Namespace -o wide
    
    Write-Host "`n=== Services ===" -ForegroundColor Cyan
    kubectl get svc -n $Namespace
    
    Write-Host "`n=== Deployments ===" -ForegroundColor Cyan
    kubectl get deployments -n $Namespace
    
    Write-Host "`n=== HPAs ===" -ForegroundColor Cyan
    kubectl get hpa -n $Namespace
    
    Write-Host "`n=== Ingress ===" -ForegroundColor Cyan
    kubectl get ingress -n $Namespace
    
    Write-Host "`n=== PVCs ===" -ForegroundColor Cyan
    kubectl get pvc -n $Namespace
    
    Write-Host "`n=== Recent Events ===" -ForegroundColor Cyan
    kubectl get events -n $Namespace --sort-by='.lastTimestamp' | Select-Object -Last 10
}

function Get-ServiceLogs {
    param([string]$ServiceName)
    
    if ([string]::IsNullOrEmpty($ServiceName)) {
        Write-Host "Available services:" -ForegroundColor Cyan
        kubectl get pods -n $Namespace -o jsonpath='{.items[*].metadata.labels.app\.kubernetes\.io/name}' | 
            ForEach-Object { $_ -split ' ' } | 
            Sort-Object -Unique
        Write-Host "`nUsage: .\deploy.ps1 -Action logs -Service <service-name>" -ForegroundColor Yellow
        return
    }
    
    Write-Header "Logs for $ServiceName"
    kubectl logs -l app.kubernetes.io/name=$ServiceName -n $Namespace --tail=100 -f
}

function Restart-Service {
    param([string]$ServiceName)
    
    if ([string]::IsNullOrEmpty($ServiceName)) {
        Write-Host "Usage: .\deploy.ps1 -Action restart -Service <service-name>" -ForegroundColor Yellow
        Write-Host "Example: .\deploy.ps1 -Action restart -Service query" -ForegroundColor Yellow
        return
    }
    
    Write-Header "Restarting $ServiceName"
    kubectl rollout restart deployment/$ServiceName -n $Namespace
    kubectl rollout status deployment/$ServiceName -n $Namespace
    Write-Host "Restart complete!" -ForegroundColor Green
}

# Main execution
if (-not (Test-Kubectl)) {
    exit 1
}

switch ($Action) {
    "apply" { Deploy-Resources }
    "delete" { Remove-Resources }
    "status" { Get-Status }
    "logs" { Get-ServiceLogs -ServiceName $Service }
    "restart" { Restart-Service -ServiceName $Service }
    default { Get-Status }
}
