#Requires -Version 5.1
<#
.SYNOPSIS
    Comprehensive Kubernetes deployment script for Cognimend RAG System

.DESCRIPTION
    This script deploys the entire RAG system to Kubernetes (Minikube) in the correct order,
    with health checks, automatic rollback on failure, and detailed progress reporting.

.PARAMETER Component
    Optional. Deploy specific components only. Comma-separated list.
    Valid values: namespace, configmap, secrets, postgres, qdrant, redis, 
                  upload, query, telemetry, drift, controller, evaluation, hpa, monitoring, ingress
    Example: -Component upload,query

.PARAMETER Namespace
    The Kubernetes namespace to deploy to. Default: cognimend

.PARAMETER DryRun
    If specified, shows what would be deployed without actually deploying.

.PARAMETER SkipPreChecks
    Skip pre-deployment checks (not recommended for production).

.PARAMETER Force
    Force deployment even if namespace exists.

.PARAMETER Timeout
    Timeout in seconds for pod readiness checks. Default: 300 (5 minutes)

.EXAMPLE
    .\deploy-to-k8s.ps1
    Deploys all components to the cognimend namespace.

.EXAMPLE
    .\deploy-to-k8s.ps1 -Component upload,query
    Deploys only upload and query services.

.EXAMPLE
    .\deploy-to-k8s.ps1 -DryRun
    Shows what would be deployed without actually deploying.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Component = "",
    
    [Parameter(Mandatory = $false)]
    [string]$Namespace = "cognimend",
    
    [Parameter(Mandatory = $false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipPreChecks,
    
    [Parameter(Mandatory = $false)]
    [switch]$Force,
    
    [Parameter(Mandatory = $false)]
    [int]$Timeout = 300
)

$ErrorActionPreference = "Stop"
$Script:StartTime = Get-Date
$Script:DeployedResources = @()
$Script:FailedResources = @()
$Script:Warnings = @()

$Script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$Script:K8sDir = Join-Path $Script:ProjectRoot "k8s"

$Script:AllComponents = @(
    "namespace",
    "configmap", 
    "secrets",
    "postgres",
    "qdrant", 
    "redis",
    "upload",
    "query",
    "telemetry",
    "drift",
    "controller",
    "evaluation",
    "hpa",
    "monitoring",
    "ingress"
)

$Script:ServicePorts = @{
    "upload-service"    = 8001
    "query-service"     = 8002
    "telemetry-service" = 8003
    "drift-detector"    = 8004
    "controller"        = 8005
    "evaluation"        = 8006
}

$Script:YamlFiles = @{
    "namespace"  = @("namespace.yaml")
    "configmap"  = @("configmap.yaml")
    "postgres"   = @("postgres-pv.yaml", "postgres-deployment.yaml")
    "qdrant"     = @("qdrant-pv.yaml", "qdrant-deployment.yaml")
    "redis"      = @("redis-deployment.yaml")
    "upload"     = @("upload-deployment.yaml")
    "query"      = @("query-deployment.yaml")
    "telemetry"  = @("telemetry-deployment.yaml")
    "drift"      = @("drift-detector-deployment.yaml")
    "controller" = @("controller-deployment.yaml")
    "evaluation" = @("evaluation-deployment.yaml")
    "hpa"        = @("query-hpa.yaml", "upload-hpa.yaml")
    "monitoring" = @("servicemonitor.yaml")
    "ingress"    = @("ingress.yaml")
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Error2 {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Write-Warning2 {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
    $Script:Warnings += $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Step {
    param(
        [int]$StepNumber,
        [int]$TotalSteps,
        [string]$Description
    )
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor DarkGray
    Write-Host "[$StepNumber/$TotalSteps] $Description" -ForegroundColor Magenta
    Write-Host "========================================================================" -ForegroundColor DarkGray
}

function Write-SubStep {
    param([string]$Message)
    Write-Host "   -> $Message" -ForegroundColor White
}

function Write-Progress2 {
    param(
        [string]$Activity,
        [int]$PercentComplete
    )
    
    $width = 40
    $complete = [math]::Floor($width * $PercentComplete / 100)
    $remaining = $width - $complete
    
    $bar = ("#" * $complete) + ("-" * $remaining)
    Write-Host "`r   [$bar] $PercentComplete% - $Activity" -NoNewline
}

function Show-Banner {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "         COGNIMEND RAG SYSTEM - Kubernetes Deployment Script           " -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-KubectlInstalled {
    try {
        $null = kubectl version --client 2>&1
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-MinikubeRunning {
    try {
        $status = minikube status --format="{{.Host}}" 2>&1
        return $status -eq "Running"
    }
    catch {
        return $false
    }
}

function Get-MinikubeIP {
    try {
        $ip = minikube ip 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $ip.Trim()
        }
        return $null
    }
    catch {
        return $null
    }
}

function Test-NamespaceExists {
    param([string]$Name)
    
    $null = kubectl get namespace $Name 2>&1
    return $LASTEXITCODE -eq 0
}

function Test-SecretExists {
    param(
        [string]$Name,
        [string]$Ns
    )
    
    $null = kubectl get secret $Name -n $Ns 2>&1
    return $LASTEXITCODE -eq 0
}

function Apply-YamlFile {
    param(
        [string]$FilePath,
        [string]$Ns = "",
        [switch]$IsDryRun
    )
    
    if (-not (Test-Path $FilePath)) {
        throw "YAML file not found: $FilePath"
    }
    
    $cmd = "kubectl apply -f `"$FilePath`""
    
    if ($Ns -and $Ns -ne "default") {
        $cmd += " -n $Ns"
    }
    
    if ($IsDryRun) {
        $cmd += " --dry-run=client"
    }
    
    Write-SubStep "Applying: $(Split-Path $FilePath -Leaf)"
    
    $output = Invoke-Expression $cmd 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to apply $FilePath : $output"
    }
    
    return $output
}

function Wait-ForPodReady {
    param(
        [string]$LabelSelector,
        [string]$Ns,
        [int]$TimeoutSeconds = 300,
        [string]$PodName = ""
    )
    
    $displayName = if ($PodName) { $PodName } else { $LabelSelector }
    Write-SubStep "Waiting for pod ($displayName) to be ready (timeout: ${TimeoutSeconds}s)..."
    
    $startTime = Get-Date
    $lastStatus = ""
    
    while ($true) {
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        
        if ($elapsed -gt $TimeoutSeconds) {
            Write-Host ""
            return @{
                Success  = $false
                Message  = "Timeout waiting for pod to be ready"
                Elapsed  = $elapsed
                TimedOut = $true
            }
        }
        
        $pods = kubectl get pods -l $LabelSelector -n $Ns -o json 2>&1 | ConvertFrom-Json
        
        if ($pods.items.Count -eq 0) {
            $status = "Pending creation..."
        }
        else {
            $pod = $pods.items[0]
            $phase = $pod.status.phase
            $ready = ($pod.status.conditions | Where-Object { $_.type -eq "Ready" }).status
            
            if ($phase -eq "Running" -and $ready -eq "True") {
                Write-Host ""
                return @{
                    Success = $true
                    Message = "Pod is ready"
                    Elapsed = $elapsed
                    PodName = $pod.metadata.name
                }
            }
            
            $containerStatus = ""
            if ($pod.status.containerStatuses) {
                $cs = $pod.status.containerStatuses[0]
                if ($cs.state.waiting) {
                    $containerStatus = $cs.state.waiting.reason
                }
            }
            
            $status = "$phase"
            if ($containerStatus) {
                $status += " ($containerStatus)"
            }
        }
        
        if ($status -ne $lastStatus) {
            Write-Host ""
            Write-SubStep "Status: $status"
            $lastStatus = $status
        }
        
        $percent = [math]::Min(100, [math]::Floor($elapsed / $TimeoutSeconds * 100))
        Write-Progress2 -Activity $status -PercentComplete $percent
        
        Start-Sleep -Seconds 2
    }
}

function Get-PodLogs {
    param(
        [string]$LabelSelector,
        [string]$Ns,
        [int]$TailLines = 50
    )
    
    try {
        $logs = kubectl logs -l $LabelSelector -n $Ns --tail=$TailLines 2>&1
        return $logs
    }
    catch {
        return "Failed to get logs: $_"
    }
}

function Invoke-Rollback {
    param([array]$Resources)
    
    Write-Host ""
    Write-Warning2 "Initiating rollback..."
    
    foreach ($resource in $Resources) {
        try {
            Write-SubStep "Deleting: $($resource.Type)/$($resource.Name)"
            $null = kubectl delete $resource.Type $resource.Name -n $Namespace --ignore-not-found 2>&1
        }
        catch {
            Write-Error2 "Failed to rollback $($resource.Name): $_"
        }
    }
    
    Write-Warning2 "Rollback completed"
}

function Invoke-PreDeploymentChecks {
    Write-Step -StepNumber 1 -TotalSteps 9 -Description "Pre-deployment Checks"
    
    Write-SubStep "Checking kubectl installation..."
    if (Test-KubectlInstalled) {
        Write-Success "kubectl is installed"
    }
    else {
        Write-Error2 "kubectl is not installed or not in PATH"
        Write-Info "Install kubectl: https://kubernetes.io/docs/tasks/tools/"
        return $false
    }
    
    Write-SubStep "Checking Minikube status..."
    if (Test-MinikubeRunning) {
        $ip = Get-MinikubeIP
        Write-Success "Minikube is running (IP: $ip)"
    }
    else {
        Write-Error2 "Minikube is not running"
        Write-Info "Start Minikube: minikube start"
        return $false
    }
    
    Write-SubStep "Checking if namespace '$Namespace' exists..."
    if (Test-NamespaceExists -Name $Namespace) {
        if ($Force) {
            Write-Warning2 "Namespace '$Namespace' already exists (continuing with -Force)"
        }
        else {
            Write-Warning2 "Namespace '$Namespace' already exists"
            Write-Info "Use -Force to continue anyway, or delete: kubectl delete namespace $Namespace"
        }
    }
    else {
        Write-Success "Namespace '$Namespace' does not exist (will be created)"
    }
    
    Write-SubStep "Validating YAML files exist..."
    $missingFiles = @()
    
    foreach ($component in $Script:YamlFiles.Keys) {
        foreach ($file in $Script:YamlFiles[$component]) {
            $filePath = Join-Path $Script:K8sDir $file
            if (-not (Test-Path $filePath)) {
                $missingFiles += $file
            }
        }
    }
    
    if ($missingFiles.Count -gt 0) {
        Write-Warning2 "Missing YAML files (some components may be skipped):"
        foreach ($file in $missingFiles) {
            Write-Host "      - $file" -ForegroundColor Yellow
        }
    }
    else {
        Write-Success "All required YAML files found"
    }
    
    if (-not (Test-Path $Script:K8sDir)) {
        Write-Error2 "K8s directory not found: $Script:K8sDir"
        return $false
    }
    
    return $true
}

function Deploy-Namespace {
    Write-Step -StepNumber 2 -TotalSteps 9 -Description "Creating Namespace"
    
    if (Test-NamespaceExists -Name $Namespace) {
        Write-Warning2 "Namespace '$Namespace' already exists, skipping creation"
        return $true
    }
    
    $nsFile = Join-Path $Script:K8sDir "namespace.yaml"
    
    if (Test-Path $nsFile) {
        try {
            Apply-YamlFile -FilePath $nsFile -IsDryRun:$DryRun
            $Script:DeployedResources += @{ Type = "namespace"; Name = $Namespace }
            Write-Success "Namespace '$Namespace' created"
            return $true
        }
        catch {
            Write-Error2 "Failed to create namespace: $_"
            return $false
        }
    }
    else {
        Write-SubStep "Creating namespace via kubectl..."
        if ($DryRun) {
            Write-Info "[DRY RUN] Would create namespace: $Namespace"
        }
        else {
            $null = kubectl create namespace $Namespace 2>&1
            if ($LASTEXITCODE -eq 0) {
                $Script:DeployedResources += @{ Type = "namespace"; Name = $Namespace }
                Write-Success "Namespace '$Namespace' created"
            }
            else {
                Write-Error2 "Failed to create namespace"
                return $false
            }
        }
        return $true
    }
}

function Deploy-ConfigMapAndSecrets {
    Write-Step -StepNumber 3 -TotalSteps 9 -Description "Creating ConfigMap and Secrets"
    
    $configMapFile = Join-Path $Script:K8sDir "configmap.yaml"
    if (Test-Path $configMapFile) {
        try {
            Apply-YamlFile -FilePath $configMapFile -Ns $Namespace -IsDryRun:$DryRun
            $Script:DeployedResources += @{ Type = "configmap"; Name = "cognimend-config" }
            Write-Success "ConfigMap applied"
        }
        catch {
            Write-Error2 "Failed to apply ConfigMap: $_"
            return $false
        }
    }
    else {
        Write-Warning2 "ConfigMap file not found, skipping..."
    }
    
    Write-SubStep "Creating secrets..."
    
    if (Test-SecretExists -Name "cognimend-secrets" -Ns $Namespace) {
        Write-Warning2 "Secrets already exist. Do you want to recreate them?"
        $response = Read-Host "   Enter 'yes' to recreate, or any other key to skip"
        if ($response -ne "yes") {
            Write-Info "Keeping existing secrets"
            return $true
        }
        $null = kubectl delete secret cognimend-secrets -n $Namespace 2>&1
    }
    
    $openRouterKey = $env:OPENROUTER_API_KEY
    
    if (-not $openRouterKey) {
        Write-Warning2 "OPENROUTER_API_KEY environment variable not set"
        
        $maxAttempts = 3
        $attempt = 0
        
        while ($attempt -lt $maxAttempts) {
            $attempt++
            Write-Host ""
            $openRouterKey = Read-Host "   Enter your OPENROUTER_API_KEY (attempt $attempt/$maxAttempts)"
            
            if ($openRouterKey -and $openRouterKey.Length -gt 10) {
                break
            }
            
            Write-Warning2 "Invalid API key. Please enter a valid key."
        }
        
        if (-not $openRouterKey -or $openRouterKey.Length -le 10) {
            Write-Error2 "Failed to get valid OPENROUTER_API_KEY after $maxAttempts attempts"
            return $false
        }
    }
    
    $postgresPassword = $env:POSTGRES_PASSWORD
    if (-not $postgresPassword) {
        $postgresPassword = Read-Host "   Enter PostgreSQL password (or press Enter for 'postgres')"
        if (-not $postgresPassword) {
            $postgresPassword = "postgres"
        }
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create secret with OPENROUTER_API_KEY and POSTGRES_PASSWORD"
    }
    else {
        $result = kubectl create secret generic cognimend-secrets --from-literal=OPENROUTER_API_KEY=$openRouterKey --from-literal=POSTGRES_PASSWORD=$postgresPassword -n $Namespace 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $Script:DeployedResources += @{ Type = "secret"; Name = "cognimend-secrets" }
            Write-Success "Secrets created successfully"
        }
        else {
            Write-Error2 "Failed to create secrets: $result"
            return $false
        }
    }
    
    if (-not $DryRun) {
        Write-SubStep "Verifying secrets..."
        $null = kubectl get secret cognimend-secrets -n $Namespace -o jsonpath="{.data}" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Secrets verified"
        }
        else {
            Write-Warning2 "Could not verify secrets"
        }
    }
    
    return $true
}

function Deploy-Databases {
    Write-Step -StepNumber 4 -TotalSteps 9 -Description "Deploying Databases"
    
    $databases = @(
        @{
            Name     = "PostgreSQL"
            Files    = @("postgres-pv.yaml", "postgres-deployment.yaml")
            Selector = "app=postgres"
            Required = $true
        },
        @{
            Name     = "Qdrant"
            Files    = @("qdrant-pv.yaml", "qdrant-deployment.yaml")
            Selector = "app=qdrant"
            Required = $true
        },
        @{
            Name     = "Redis"
            Files    = @("redis-deployment.yaml")
            Selector = "app=redis"
            Required = $true
        }
    )
    
    foreach ($db in $databases) {
        Write-Host ""
        Write-Host "   Deploying $($db.Name)..." -ForegroundColor White
        
        foreach ($file in $db.Files) {
            $filePath = Join-Path $Script:K8sDir $file
            if (Test-Path $filePath) {
                try {
                    Apply-YamlFile -FilePath $filePath -Ns $Namespace -IsDryRun:$DryRun
                }
                catch {
                    Write-Error2 "Failed to apply $file : $_"
                    if ($db.Required) {
                        return $false
                    }
                }
            }
            else {
                Write-Warning2 "File not found: $file"
            }
        }
        
        if (-not $DryRun) {
            $result = Wait-ForPodReady -LabelSelector $db.Selector -Ns $Namespace -TimeoutSeconds $Timeout -PodName $db.Name
            
            if ($result.Success) {
                Write-Success "$($db.Name) is ready (took $([math]::Round($result.Elapsed, 1))s)"
                $Script:DeployedResources += @{ Type = "deployment"; Name = $db.Name.ToLower() }
            }
            else {
                if ($result.TimedOut) {
                    Write-Warning2 "$($db.Name) timed out waiting for readiness"
                    Write-Host ""
                    $response = Read-Host "   Continue waiting (w), Skip (s), or Abort (a)?"
                    
                    switch ($response.ToLower()) {
                        "w" {
                            $result = Wait-ForPodReady -LabelSelector $db.Selector -Ns $Namespace -TimeoutSeconds ($Timeout * 2) -PodName $db.Name
                            if (-not $result.Success) {
                                Write-Error2 "$($db.Name) still not ready after extended wait"
                                Write-Info "Pod logs:"
                                $logs = Get-PodLogs -LabelSelector $db.Selector -Ns $Namespace
                                Write-Host $logs
                                return $false
                            }
                        }
                        "s" {
                            Write-Warning2 "Skipping $($db.Name) readiness check"
                        }
                        default {
                            Write-Error2 "Aborting deployment"
                            return $false
                        }
                    }
                }
                else {
                    Write-Error2 "$($db.Name) failed to start: $($result.Message)"
                    Write-Info "Pod logs:"
                    $logs = Get-PodLogs -LabelSelector $db.Selector -Ns $Namespace
                    Write-Host $logs
                    return $false
                }
            }
        }
    }
    
    if (-not $DryRun) {
        Write-Host ""
        Write-SubStep "Database pod status:"
        kubectl get pods -n $Namespace -l "app in (postgres,qdrant,redis)" -o wide
    }
    
    return $true
}

function Deploy-ApplicationServices {
    Write-Step -StepNumber 5 -TotalSteps 9 -Description "Deploying Application Services"
    
    $services = @(
        @{ Name = "upload-service"; File = "upload-deployment.yaml"; Selector = "app=upload-service" },
        @{ Name = "query-service"; File = "query-deployment.yaml"; Selector = "app=query-service" },
        @{ Name = "telemetry-service"; File = "telemetry-deployment.yaml"; Selector = "app=telemetry-service" },
        @{ Name = "drift-detector"; File = "drift-detector-deployment.yaml"; Selector = "app=drift-detector" },
        @{ Name = "controller"; File = "controller-deployment.yaml"; Selector = "app=controller" },
        @{ Name = "evaluation"; File = "evaluation-deployment.yaml"; Selector = "app=evaluation" }
    )
    
    foreach ($service in $services) {
        $filePath = Join-Path $Script:K8sDir $service.File
        
        if (Test-Path $filePath) {
            Write-Host "   Deploying $($service.Name)..." -ForegroundColor White
            try {
                Apply-YamlFile -FilePath $filePath -Ns $Namespace -IsDryRun:$DryRun
                $Script:DeployedResources += @{ Type = "deployment"; Name = $service.Name }
            }
            catch {
                Write-Error2 "Failed to deploy $($service.Name): $_"
                $Script:FailedResources += $service.Name
            }
        }
        else {
            Write-Warning2 "Deployment file not found: $($service.File)"
        }
    }
    
    if (-not $DryRun) {
        Write-Host ""
        Write-SubStep "Waiting for all application pods to be ready..."
        
        foreach ($service in $services) {
            $filePath = Join-Path $Script:K8sDir $service.File
            if (Test-Path $filePath) {
                $result = Wait-ForPodReady -LabelSelector $service.Selector -Ns $Namespace -TimeoutSeconds 180 -PodName $service.Name
                
                if ($result.Success) {
                    Write-Success "$($service.Name) is ready"
                }
                else {
                    Write-Warning2 "$($service.Name) may not be fully ready"
                    $Script:Warnings += "$($service.Name) readiness check failed"
                }
            }
        }
        
        Write-Host ""
        Write-SubStep "Application pod status:"
        kubectl get pods -n $Namespace -o wide
    }
    
    return ($Script:FailedResources.Count -eq 0)
}

function Deploy-HPA {
    Write-Step -StepNumber 6 -TotalSteps 9 -Description "Deploying Horizontal Pod Autoscalers"
    
    $hpaFiles = @("query-hpa.yaml", "upload-hpa.yaml")
    
    foreach ($file in $hpaFiles) {
        $filePath = Join-Path $Script:K8sDir $file
        
        if (Test-Path $filePath) {
            try {
                Apply-YamlFile -FilePath $filePath -Ns $Namespace -IsDryRun:$DryRun
                $Script:DeployedResources += @{ Type = "hpa"; Name = $file.Replace("-hpa.yaml", "") }
                Write-Success "Applied $file"
            }
            catch {
                Write-Warning2 "Failed to apply $file : $_"
            }
        }
        else {
            Write-Warning2 "HPA file not found: $file"
        }
    }
    
    if (-not $DryRun) {
        Write-Host ""
        Write-SubStep "HPA status:"
        kubectl get hpa -n $Namespace 2>&1
    }
    
    return $true
}

function Deploy-Monitoring {
    Write-Step -StepNumber 7 -TotalSteps 9 -Description "Deploying Monitoring (ServiceMonitor)"
    
    $smFile = Join-Path $Script:K8sDir "servicemonitor.yaml"
    
    if (Test-Path $smFile) {
        try {
            Apply-YamlFile -FilePath $smFile -Ns $Namespace -IsDryRun:$DryRun
            $Script:DeployedResources += @{ Type = "servicemonitor"; Name = "cognimend" }
            Write-Success "ServiceMonitor applied"
        }
        catch {
            Write-Warning2 "Failed to apply ServiceMonitor: $_"
            Write-Info "Note: ServiceMonitor requires Prometheus Operator to be installed"
        }
    }
    else {
        Write-Warning2 "ServiceMonitor file not found"
    }
    
    if (-not $DryRun) {
        Write-Host ""
        Write-SubStep "Monitoring endpoints:"
        Write-Host "      - Prometheus metrics: http://<service>:<port>/metrics" -ForegroundColor Gray
        Write-Host "      - Health check: http://<service>:<port>/health" -ForegroundColor Gray
        
        foreach ($svc in $Script:ServicePorts.Keys) {
            $port = $Script:ServicePorts[$svc]
            Write-Host "      - $svc : /metrics (port $port)" -ForegroundColor Gray
        }
    }
    
    return $true
}

function Deploy-Ingress {
    Write-Step -StepNumber 8 -TotalSteps 9 -Description "Deploying Ingress"
    
    $ingressFile = Join-Path $Script:K8sDir "ingress.yaml"
    
    if (Test-Path $ingressFile) {
        try {
            Apply-YamlFile -FilePath $ingressFile -Ns $Namespace -IsDryRun:$DryRun
            $Script:DeployedResources += @{ Type = "ingress"; Name = "cognimend-ingress" }
            Write-Success "Ingress applied"
        }
        catch {
            Write-Warning2 "Failed to apply Ingress: $_"
        }
    }
    else {
        Write-Warning2 "Ingress file not found"
    }
    
    if (-not $DryRun) {
        $minikubeIP = Get-MinikubeIP
        
        if ($minikubeIP) {
            Write-Host ""
            Write-SubStep "Access URLs (add to /etc/hosts if using hostname):"
            Write-Host "      - Frontend:   http://$minikubeIP/" -ForegroundColor Green
            Write-Host "      - Upload API: http://$minikubeIP/api/upload" -ForegroundColor Green
            Write-Host "      - Query API:  http://$minikubeIP/api/query" -ForegroundColor Green
            Write-Host "      - Metrics:    http://$minikubeIP/api/metrics" -ForegroundColor Green
            
            Write-Host ""
            Write-Info "Enable Minikube ingress addon if not already enabled:"
            Write-Host "      minikube addons enable ingress" -ForegroundColor Yellow
        }
    }
    
    return $true
}

function Invoke-PostDeploymentVerification {
    Write-Step -StepNumber 9 -TotalSteps 9 -Description "Post-deployment Verification"
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Skipping post-deployment verification"
        return $true
    }
    
    Write-SubStep "Fetching all resources in namespace '$Namespace'..."
    Write-Host ""
    kubectl get all -n $Namespace
    
    Write-Host ""
    Write-SubStep "Pod Status Summary:"
    $pods = kubectl get pods -n $Namespace -o json 2>&1 | ConvertFrom-Json
    
    if ($pods.items) {
        $statusTable = @()
        foreach ($pod in $pods.items) {
            $ready = ($pod.status.conditions | Where-Object { $_.type -eq "Ready" }).status
            $restarts = 0
            if ($pod.status.containerStatuses) {
                $restarts = ($pod.status.containerStatuses | Measure-Object -Property restartCount -Sum).Sum
            }
            $statusTable += [PSCustomObject]@{
                Name     = $pod.metadata.name
                Status   = $pod.status.phase
                Ready    = $ready
                Restarts = $restarts
            }
        }
        
        $statusTable | Format-Table -AutoSize
    }
    
    Write-SubStep "Service Endpoints:"
    kubectl get svc -n $Namespace -o wide
    
    Write-Host ""
    Write-SubStep "Testing health endpoints..."
    
    $healthResults = @()
    
    foreach ($svc in $Script:ServicePorts.Keys) {
        $port = $Script:ServicePorts[$svc]
        
        try {
            $null = kubectl get svc $svc -n $Namespace -o json 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                $healthResults += [PSCustomObject]@{
                    Service = $svc
                    Port    = $port
                    Status  = "Available"
                }
            }
            else {
                $healthResults += [PSCustomObject]@{
                    Service = $svc
                    Port    = $port
                    Status  = "Not Found"
                }
            }
        }
        catch {
            $healthResults += [PSCustomObject]@{
                Service = $svc
                Port    = $port
                Status  = "Unknown"
            }
        }
    }
    
    $healthResults | Format-Table -AutoSize
    
    return $true
}

function Show-Summary {
    $duration = (Get-Date) - $Script:StartTime
    $minikubeIP = Get-MinikubeIP
    
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "                        DEPLOYMENT SUMMARY                              " -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Deployment Statistics:" -ForegroundColor White
    Write-Host "   - Namespace: $Namespace" -ForegroundColor Gray
    Write-Host "   - Duration: $([math]::Round($duration.TotalMinutes, 2)) minutes" -ForegroundColor Gray
    Write-Host "   - Resources Deployed: $($Script:DeployedResources.Count)" -ForegroundColor Gray
    Write-Host "   - Warnings: $($Script:Warnings.Count)" -ForegroundColor Gray
    Write-Host "   - Failed: $($Script:FailedResources.Count)" -ForegroundColor Gray
    
    if ($Script:Warnings.Count -gt 0) {
        Write-Host ""
        Write-Host "Warnings:" -ForegroundColor Yellow
        foreach ($warning in $Script:Warnings) {
            Write-Host "   - $warning" -ForegroundColor Yellow
        }
    }
    
    if ($Script:FailedResources.Count -gt 0) {
        Write-Host ""
        Write-Host "Failed Resources:" -ForegroundColor Red
        foreach ($failed in $Script:FailedResources) {
            Write-Host "   - $failed" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "                    DEPLOYMENT COMPLETE!                                " -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access URLs:" -ForegroundColor Cyan
    Write-Host "   - Frontend:        http://$minikubeIP/" -ForegroundColor White
    Write-Host "   - Upload API:      http://$minikubeIP:8001 or via Ingress" -ForegroundColor White
    Write-Host "   - Query API:       http://$minikubeIP:8002 or via Ingress" -ForegroundColor White
    Write-Host "   - Telemetry:       http://$minikubeIP:8003" -ForegroundColor White
    Write-Host ""
    Write-Host "Useful Commands:" -ForegroundColor Cyan
    Write-Host "   kubectl get pods -n $Namespace" -ForegroundColor Gray
    Write-Host "   kubectl logs -f <pod-name> -n $Namespace" -ForegroundColor Gray
    Write-Host "   kubectl port-forward svc/query-service 8002:8002 -n $Namespace" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Monitoring:" -ForegroundColor Cyan
    Write-Host "   - Prometheus:      kubectl port-forward svc/prometheus 9090:9090" -ForegroundColor Gray
    Write-Host "   - Grafana:         kubectl port-forward svc/grafana 3000:3000" -ForegroundColor Gray
    Write-Host "   - Jaeger:          kubectl port-forward svc/jaeger 16686:16686" -ForegroundColor Gray
    Write-Host ""
}

function Main {
    Show-Banner
    
    $selectedComponents = @()
    if ($Component) {
        $selectedComponents = $Component.Split(",") | ForEach-Object { $_.Trim().ToLower() }
        Write-Info "Deploying selected components: $($selectedComponents -join ', ')"
    }
    else {
        $selectedComponents = $Script:AllComponents
        Write-Info "Deploying all components"
    }
    
    if ($DryRun) {
        Write-Warning2 "DRY RUN MODE - No changes will be made"
    }
    
    Write-Host ""
    Write-Host "Configuration:" -ForegroundColor White
    Write-Host "   - Namespace: $Namespace" -ForegroundColor Gray
    Write-Host "   - K8s Directory: $Script:K8sDir" -ForegroundColor Gray
    Write-Host "   - Timeout: ${Timeout}s" -ForegroundColor Gray
    Write-Host ""
    
    try {
        if (-not $SkipPreChecks) {
            if (-not (Invoke-PreDeploymentChecks)) {
                Write-Error2 "Pre-deployment checks failed. Aborting."
                exit 1
            }
        }
        else {
            Write-Warning2 "Skipping pre-deployment checks (not recommended)"
        }
        
        if ($selectedComponents -contains "namespace" -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-Namespace)) {
                throw "Failed to create namespace"
            }
        }
        
        if ($selectedComponents -contains "configmap" -or $selectedComponents -contains "secrets" -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-ConfigMapAndSecrets)) {
                throw "Failed to create ConfigMap or Secrets"
            }
        }
        
        $dbComponents = @("postgres", "qdrant", "redis")
        if (($selectedComponents | Where-Object { $dbComponents -contains $_ }).Count -gt 0 -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-Databases)) {
                throw "Failed to deploy databases"
            }
        }
        
        $appComponents = @("upload", "query", "telemetry", "drift", "controller", "evaluation")
        if (($selectedComponents | Where-Object { $appComponents -contains $_ }).Count -gt 0 -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-ApplicationServices)) {
                Write-Warning2 "Some application services may have failed to deploy"
            }
        }
        
        if ($selectedComponents -contains "hpa" -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-HPA)) {
                Write-Warning2 "HPA deployment had issues"
            }
        }
        
        if ($selectedComponents -contains "monitoring" -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-Monitoring)) {
                Write-Warning2 "Monitoring deployment had issues"
            }
        }
        
        if ($selectedComponents -contains "ingress" -or $selectedComponents.Count -eq $Script:AllComponents.Count) {
            if (-not (Deploy-Ingress)) {
                Write-Warning2 "Ingress deployment had issues"
            }
        }
        
        Invoke-PostDeploymentVerification
        
        Show-Summary
        
    }
    catch {
        Write-Host ""
        Write-Error2 "Deployment failed: $_"
        Write-Host ""
        
        if ($Script:DeployedResources.Count -gt 0 -and -not $DryRun) {
            Write-Warning2 "Would you like to rollback deployed resources?"
            $response = Read-Host "   Enter 'yes' to rollback, or any other key to exit"
            
            if ($response -eq "yes") {
                Invoke-Rollback -Resources $Script:DeployedResources
            }
        }
        
        exit 1
    }
}

Main
