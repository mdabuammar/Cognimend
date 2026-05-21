#Requires -Version 5.1
<#
.SYNOPSIS
    Verifies the Minikube/Kubernetes environment is properly configured.

.DESCRIPTION
    This script performs comprehensive checks on the local Kubernetes
    development environment including Minikube status, kubectl connectivity,
    available resources, and installed addons.

.PARAMETER Detailed
    Show detailed output for each check.

.NOTES
    Author: RAG System DevOps
    Version: 1.0
    Date: 2026-01-31
#>

param(
    [switch]$Detailed
)

# Colors and formatting
$SuccessColor = "Green"
$ErrorColor = "Red"
$WarningColor = "Yellow"
$InfoColor = "Cyan"

# Track overall status
$script:TotalChecks = 0
$script:PassedChecks = 0
$script:WarningChecks = 0
$script:FailedChecks = 0

function Write-Status {
    param(
        [string]$Message,
        [ValidateSet("Success", "Error", "Warning", "Info")]
        [string]$Type = "Info"
    )
    
    switch ($Type) {
        "Success" { 
            Write-Host "[OK] $Message" -ForegroundColor $SuccessColor 
            $script:PassedChecks++
        }
        "Error" { 
            Write-Host "[FAIL] $Message" -ForegroundColor $ErrorColor 
            $script:FailedChecks++
        }
        "Warning" { 
            Write-Host "[WARN] $Message" -ForegroundColor $WarningColor 
            $script:WarningChecks++
        }
        "Info" { 
            Write-Host "[INFO] $Message" -ForegroundColor $InfoColor 
        }
    }
}

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-SubHeader {
    param([string]$Title)
    Write-Host ""
    Write-Host "--- $Title ---" -ForegroundColor White
}

function Test-DockerDesktop {
    $script:TotalChecks++
    
    Write-Host "Checking Docker Desktop..." -ForegroundColor Gray
    
    # Check if Docker CLI is available
    $dockerCli = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCli) {
        Write-Status "Docker CLI not found" -Type Error
        return $false
    }
    
    # Check if Docker daemon is running
    try {
        $null = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            if ($Detailed) {
                $version = docker version --format "{{.Server.Version}}" 2>$null
                Write-Host "  Docker Server Version: $version" -ForegroundColor Gray
            }
            Write-Status "Docker Desktop is running" -Type Success
            return $true
        }
    }
    catch {
        # Fall through to error
    }
    
    Write-Status "Docker Desktop is not running. Please start it first." -Type Error
    return $false
}

function Test-MinikubeInstallation {
    $script:TotalChecks++
    
    Write-Host "Checking Minikube installation..." -ForegroundColor Gray
    
    $minikube = Get-Command minikube -ErrorAction SilentlyContinue
    if (-not $minikube) {
        Write-Status "Minikube is not installed" -Type Error
        Write-Host "  Install with: winget install Kubernetes.minikube" -ForegroundColor Yellow
        return $false
    }
    
    $version = minikube version --short 2>$null
    if ($Detailed) {
        Write-Host "  Version: $version" -ForegroundColor Gray
        Write-Host "  Path: $($minikube.Source)" -ForegroundColor Gray
    }
    
    Write-Status "Minikube installed ($version)" -Type Success
    return $true
}

function Test-MinikubeStatus {
    $script:TotalChecks++
    
    Write-Host "Checking Minikube cluster status..." -ForegroundColor Gray
    
    try {
        $status = minikube status --format="{{.Host}}" 2>&1
        
        if ($status -eq "Running") {
            if ($Detailed) {
                $profile = minikube profile 2>$null
                Write-Host "  Profile: $profile" -ForegroundColor Gray
                
                $ip = minikube ip 2>$null
                Write-Host "  IP Address: $ip" -ForegroundColor Gray
            }
            Write-Status "Minikube cluster is running" -Type Success
            return $true
        }
        elseif ($status -eq "Stopped") {
            Write-Status "Minikube cluster is stopped. Run: minikube start" -Type Warning
            return $false
        }
        else {
            Write-Status "Minikube cluster not found. Run: .\scripts\setup-minikube.ps1" -Type Error
            return $false
        }
    }
    catch {
        Write-Status "Failed to check Minikube status: $_" -Type Error
        return $false
    }
}

function Test-KubectlInstallation {
    $script:TotalChecks++
    
    Write-Host "Checking kubectl installation..." -ForegroundColor Gray
    
    $kubectl = Get-Command kubectl -ErrorAction SilentlyContinue
    if (-not $kubectl) {
        Write-Status "kubectl is not installed" -Type Error
        return $false
    }
    
    $version = kubectl version --client --short 2>$null
    if ($Detailed) {
        Write-Host "  Client Version: $version" -ForegroundColor Gray
        Write-Host "  Path: $($kubectl.Source)" -ForegroundColor Gray
    }
    
    Write-Status "kubectl installed ($version)" -Type Success
    return $true
}

function Test-KubectlConnectivity {
    $script:TotalChecks++
    
    Write-Host "Checking kubectl connectivity to cluster..." -ForegroundColor Gray
    
    try {
        $context = kubectl config current-context 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Status "No kubectl context configured" -Type Error
            return $false
        }
        
        if ($Detailed) {
            Write-Host "  Current Context: $context" -ForegroundColor Gray
        }
        
        # Test actual connectivity
        $nodes = kubectl get nodes --no-headers 2>&1
        if ($LASTEXITCODE -eq 0) {
            if ($Detailed) {
                Write-Host "  Cluster nodes:" -ForegroundColor Gray
                kubectl get nodes -o wide | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
            Write-Status "kubectl connected to cluster (context: $context)" -Type Success
            return $true
        }
        else {
            Write-Status "kubectl cannot connect to cluster" -Type Error
            return $false
        }
    }
    catch {
        Write-Status "kubectl connectivity check failed: $_" -Type Error
        return $false
    }
}

function Test-HelmInstallation {
    $script:TotalChecks++
    
    Write-Host "Checking Helm installation..." -ForegroundColor Gray
    
    $helm = Get-Command helm -ErrorAction SilentlyContinue
    if (-not $helm) {
        Write-Status "Helm is not installed (optional but recommended)" -Type Warning
        Write-Host "  Install with: winget install Helm.Helm" -ForegroundColor Yellow
        return $false
    }
    
    $version = helm version --short 2>$null
    if ($Detailed) {
        Write-Host "  Version: $version" -ForegroundColor Gray
        Write-Host "  Path: $($helm.Source)" -ForegroundColor Gray
    }
    
    Write-Status "Helm installed ($version)" -Type Success
    return $true
}

function Test-MinikubeAddons {
    $script:TotalChecks++
    
    Write-Host "Checking Minikube addons..." -ForegroundColor Gray
    
    $requiredAddons = @("metrics-server", "ingress")
    $optionalAddons = @("dashboard", "storage-provisioner")
    
    try {
        $addonList = minikube addons list 2>&1
        
        $missingRequired = @()
        $missingOptional = @()
        
        foreach ($addon in $requiredAddons) {
            if ($addonList -match "$addon.*enabled") {
                if ($Detailed) {
                    Write-Host "  + $addon (required)" -ForegroundColor Green
                }
            }
            else {
                $missingRequired += $addon
                if ($Detailed) {
                    Write-Host "  - $addon (required - MISSING)" -ForegroundColor Red
                }
            }
        }
        
        foreach ($addon in $optionalAddons) {
            if ($addonList -match "$addon.*enabled") {
                if ($Detailed) {
                    Write-Host "  + $addon (optional)" -ForegroundColor Green
                }
            }
            else {
                $missingOptional += $addon
                if ($Detailed) {
                    Write-Host "  o $addon (optional - not enabled)" -ForegroundColor Gray
                }
            }
        }
        
        if ($missingRequired.Count -gt 0) {
            Write-Status "Missing required addons: $($missingRequired -join ', ')" -Type Error
            Write-Host "  Enable with: minikube addons enable <addon-name>" -ForegroundColor Yellow
            return $false
        }
        
        if ($missingOptional.Count -gt 0 -and -not $Detailed) {
            Write-Status "Required addons enabled (some optional addons not enabled)" -Type Success
        }
        else {
            Write-Status "Required addons enabled" -Type Success
        }
        
        return $true
    }
    catch {
        Write-Status "Failed to check addons: $_" -Type Error
        return $false
    }
}

function Test-ClusterResources {
    $script:TotalChecks++
    
    Write-Host "Checking cluster resources..." -ForegroundColor Gray
    
    try {
        # Get Minikube config
        $cpus = minikube config get cpus 2>$null
        $memory = minikube config get memory 2>$null
        
        # Get node resources from kubectl
        $nodeInfo = kubectl describe node minikube 2>$null
        
        if ($Detailed -or $true) {
            # Parse allocatable resources
            $cpuAllocatable = ($nodeInfo | Select-String "Allocatable:" -Context 0, 5 | Out-String)
            Write-Host "  Node Resources:" -ForegroundColor Gray
            
            # Get node capacity
            $capacityLines = kubectl get node minikube -o jsonpath="{.status.capacity}" 2>$null | ConvertFrom-Json
            if ($capacityLines) {
                Write-Host "    CPU: $($capacityLines.cpu)" -ForegroundColor Gray
                Write-Host "    Memory: $($capacityLines.memory)" -ForegroundColor Gray
                Write-Host "    Pods: $($capacityLines.pods)" -ForegroundColor Gray
            }
        }
        
        # Check metrics server
        $metricsAvailable = kubectl top nodes 2>&1
        if ($LASTEXITCODE -eq 0) {
            if ($Detailed) {
                Write-Host "  Current Usage:" -ForegroundColor Gray
                $metricsAvailable | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
            Write-Status "Cluster resources available and metrics working" -Type Success
        }
        else {
            Write-Status "Cluster resources available (metrics-server may be starting)" -Type Success
        }
        
        return $true
    }
    catch {
        Write-Status "Failed to check resources: $_" -Type Warning
        return $false
    }
}

function Test-SystemPods {
    $script:TotalChecks++
    
    Write-Host "Checking system pods..." -ForegroundColor Gray
    
    try {
        $pods = kubectl get pods -n kube-system --no-headers 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Status "Cannot retrieve system pods" -Type Error
            return $false
        }
        
        $runningPods = ($pods | Select-String "Running").Count
        $totalPods = ($pods | Measure-Object -Line).Lines
        
        if ($Detailed) {
            Write-Host "  System pods status:" -ForegroundColor Gray
            kubectl get pods -n kube-system -o wide | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        
        if ($runningPods -eq $totalPods) {
            Write-Status "All $totalPods system pods running" -Type Success
            return $true
        }
        else {
            Write-Status "$runningPods/$totalPods system pods running" -Type Warning
            return $true
        }
    }
    catch {
        Write-Status "Failed to check system pods: $_" -Type Error
        return $false
    }
}

function Test-StorageClass {
    $script:TotalChecks++
    
    Write-Host "Checking storage classes..." -ForegroundColor Gray
    
    try {
        $storageClasses = kubectl get storageclass --no-headers 2>&1
        
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($storageClasses)) {
            Write-Status "No storage classes available" -Type Warning
            return $false
        }
        
        $defaultSc = kubectl get storageclass -o jsonpath="{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class==\"true\")].metadata.name}" 2>$null
        
        if ($Detailed) {
            Write-Host "  Available storage classes:" -ForegroundColor Gray
            kubectl get storageclass | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        
        if ($defaultSc) {
            Write-Status "Default storage class available ($defaultSc)" -Type Success
        }
        else {
            Write-Status "Storage classes available (no default set)" -Type Success
        }
        
        return $true
    }
    catch {
        Write-Status "Failed to check storage classes: $_" -Type Warning
        return $false
    }
}

function Test-IngressController {
    $script:TotalChecks++
    
    Write-Host "Checking Ingress controller..." -ForegroundColor Gray
    
    try {
        $ingressPods = kubectl get pods -n ingress-nginx --no-headers 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            # Check if addon is enabled but pods not yet running
            $addonEnabled = minikube addons list 2>&1 | Select-String "ingress.*enabled"
            if ($addonEnabled) {
                Write-Status "Ingress addon enabled (controller may be starting)" -Type Warning
                return $true
            }
            Write-Status "Ingress controller not found" -Type Warning
            Write-Host "  Enable with: minikube addons enable ingress" -ForegroundColor Yellow
            return $false
        }
        
        $runningPods = ($ingressPods | Select-String "Running").Count
        
        if ($Detailed) {
            Write-Host "  Ingress controller pods:" -ForegroundColor Gray
            kubectl get pods -n ingress-nginx | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        
        if ($runningPods -gt 0) {
            Write-Status "Ingress controller running ($runningPods pods)" -Type Success
            return $true
        }
        else {
            Write-Status "Ingress controller pods not ready" -Type Warning
            return $true
        }
    }
    catch {
        Write-Status "Failed to check Ingress controller: $_" -Type Warning
        return $false
    }
}

function Show-Summary {
    Write-Header "Environment Verification Summary"
    
    $total = $script:TotalChecks
    $passed = $script:PassedChecks
    $warnings = $script:WarningChecks
    $failed = $script:FailedChecks
    
    Write-Host "Total Checks:  $total" -ForegroundColor White
    Write-Host "Passed:        $passed" -ForegroundColor Green
    Write-Host "Warnings:      $warnings" -ForegroundColor Yellow
    Write-Host "Failed:        $failed" -ForegroundColor Red
    Write-Host ""
    
    if ($failed -eq 0 -and $warnings -eq 0) {
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host "  All checks passed! Environment is ready for deployment." -ForegroundColor Green
        Write-Host "================================================================" -ForegroundColor Green
    }
    elseif ($failed -eq 0) {
        Write-Host "================================================================" -ForegroundColor Yellow
        Write-Host "  Environment ready with some warnings." -ForegroundColor Yellow
        Write-Host "================================================================" -ForegroundColor Yellow
    }
    else {
        Write-Host "================================================================" -ForegroundColor Red
        Write-Host "  Some checks failed. Please resolve issues before deploying." -ForegroundColor Red
        Write-Host "================================================================" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Quick Commands:" -ForegroundColor Cyan
    Write-Host "  .\scripts\setup-minikube.ps1      - Setup/repair Minikube" -ForegroundColor Gray
    Write-Host "  minikube start                    - Start cluster" -ForegroundColor Gray
    Write-Host "  minikube dashboard                - Open dashboard" -ForegroundColor Gray
    Write-Host "  kubectl get all -A                - List all resources" -ForegroundColor Gray
    Write-Host ""
}

# ============================================================================
# Main Script Execution
# ============================================================================

Write-Header "Kubernetes Environment Verification"
Write-Host "Running comprehensive environment checks..."
if ($Detailed) {
    Write-Host "(Detailed mode enabled)" -ForegroundColor Gray
}
Write-Host ""

# Run all checks
Write-SubHeader "Prerequisites"
Test-DockerDesktop
Test-MinikubeInstallation
Test-KubectlInstallation
Test-HelmInstallation

Write-SubHeader "Cluster Status"
$clusterRunning = Test-MinikubeStatus

if ($clusterRunning) {
    Test-KubectlConnectivity
    
    Write-SubHeader "Cluster Configuration"
    Test-MinikubeAddons
    Test-ClusterResources
    Test-StorageClass
    
    Write-SubHeader "Workloads"
    Test-SystemPods
    Test-IngressController
}
else {
    Write-Host ""
    Write-Host "Skipping cluster checks - Minikube is not running" -ForegroundColor Yellow
}

# Show summary
Show-Summary

# Return exit code based on results
if ($script:FailedChecks -gt 0) {
    exit 1
}
exit 0
