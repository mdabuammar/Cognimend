#Requires -Version 5.1
<#
.SYNOPSIS
    Sets up Minikube for local Kubernetes development.

.DESCRIPTION
    This script installs and configures Minikube with proper resources,
    enables required addons, and verifies the cluster is ready.

.NOTES
    Author: RAG System DevOps
    Version: 1.0
    Date: 2026-01-31
#>

param(
    [int]$CPUs = 4,
    [string]$Memory = "8192",
    [string]$DiskSize = "40g",
    [string]$Driver = "docker",
    [switch]$Force
)

# Colors and formatting
$SuccessColor = "Green"
$ErrorColor = "Red"
$WarningColor = "Yellow"
$InfoColor = "Cyan"

function Write-Status {
    param(
        [string]$Message,
        [ValidateSet("Success", "Error", "Warning", "Info")]
        [string]$Type = "Info"
    )
    
    switch ($Type) {
        "Success" { Write-Host "[OK] $Message" -ForegroundColor $SuccessColor }
        "Error"   { Write-Host "[FAIL] $Message" -ForegroundColor $ErrorColor }
        "Warning" { Write-Host "[WARN] $Message" -ForegroundColor $WarningColor }
        "Info"    { Write-Host "[INFO] $Message" -ForegroundColor $InfoColor }
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

function Test-Administrator {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-DockerRunning {
    try {
        $null = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

function Install-Minikube {
    Write-Status "Installing Minikube..." -Type Info
    
    # Check if winget is available
    $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
    
    if ($wingetAvailable) {
        Write-Status "Using winget to install Minikube..." -Type Info
        winget install Kubernetes.minikube --accept-source-agreements --accept-package-agreements
        
        if ($LASTEXITCODE -eq 0) {
            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            Write-Status "Minikube installed successfully via winget" -Type Success
            return $true
        }
    }
    
    # Fallback to Chocolatey
    $chocoAvailable = Get-Command choco -ErrorAction SilentlyContinue
    if ($chocoAvailable) {
        Write-Status "Using Chocolatey to install Minikube..." -Type Info
        choco install minikube -y
        
        if ($LASTEXITCODE -eq 0) {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            Write-Status "Minikube installed successfully via Chocolatey" -Type Success
            return $true
        }
    }
    
    # Manual installation instructions
    Write-Status "Automatic installation failed. Please install manually:" -Type Warning
    Write-Host ""
    Write-Host "  Option 1 - Using winget (recommended):" -ForegroundColor Yellow
    Write-Host "      winget install Kubernetes.minikube" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 2 - Using Chocolatey:" -ForegroundColor Yellow
    Write-Host "      choco install minikube" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 3 - Direct download:" -ForegroundColor Yellow
    Write-Host "      1. Download from: https://minikube.sigs.k8s.io/docs/start/" -ForegroundColor Yellow
    Write-Host "      2. Run the installer" -ForegroundColor Yellow
    Write-Host "      3. Add to PATH if not done automatically" -ForegroundColor Yellow
    Write-Host ""
    return $false
}

function Install-Helm {
    Write-Status "Installing Helm..." -Type Info
    
    $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
    
    if ($wingetAvailable) {
        Write-Status "Using winget to install Helm..." -Type Info
        winget install Helm.Helm --accept-source-agreements --accept-package-agreements
        
        if ($LASTEXITCODE -eq 0) {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            Write-Status "Helm installed successfully via winget" -Type Success
            return $true
        }
    }
    
    $chocoAvailable = Get-Command choco -ErrorAction SilentlyContinue
    if ($chocoAvailable) {
        Write-Status "Using Chocolatey to install Helm..." -Type Info
        choco install kubernetes-helm -y
        
        if ($LASTEXITCODE -eq 0) {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            Write-Status "Helm installed successfully via Chocolatey" -Type Success
            return $true
        }
    }
    
    Write-Status "Automatic installation failed. Please install manually:" -Type Warning
    Write-Host ""
    Write-Host "  Option 1 - Using winget:" -ForegroundColor Yellow
    Write-Host "      winget install Helm.Helm" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 2 - Using Chocolatey:" -ForegroundColor Yellow
    Write-Host "      choco install kubernetes-helm" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 3 - Direct download:" -ForegroundColor Yellow
    Write-Host "      https://helm.sh/docs/intro/install/" -ForegroundColor Yellow
    Write-Host ""
    return $false
}

function Start-MinikubeCluster {
    param(
        [int]$CPUs,
        [string]$Memory,
        [string]$DiskSize,
        [string]$Driver
    )
    
    Write-Status "Starting Minikube cluster..." -Type Info
    Write-Host "  CPUs: $CPUs, Memory: ${Memory}MB, Disk: $DiskSize, Driver: $Driver" -ForegroundColor Gray
    
    $startArgs = @(
        "start",
        "--cpus=$CPUs",
        "--memory=$Memory",
        "--disk-size=$DiskSize",
        "--driver=$Driver",
        "--container-runtime=docker"
    )
    
    $process = Start-Process -FilePath "minikube" -ArgumentList $startArgs -NoNewWindow -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Status "Minikube started successfully" -Type Success
        return $true
    }
    else {
        Write-Status "Failed to start Minikube (Exit code: $($process.ExitCode))" -Type Error
        return $false
    }
}

function Enable-MinikubeAddons {
    $addons = @(
        "metrics-server",
        "ingress",
        "dashboard",
        "storage-provisioner"
    )
    
    Write-Status "Enabling Minikube addons..." -Type Info
    
    foreach ($addon in $addons) {
        Write-Host "  Enabling addon: $addon" -ForegroundColor Gray
        $null = minikube addons enable $addon 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    + $addon enabled" -ForegroundColor Green
        }
        else {
            Write-Host "    - Failed to enable $addon" -ForegroundColor Red
        }
    }
    
    Write-Status "Addons configuration complete" -Type Success
}

function Set-KubectlContext {
    Write-Status "Configuring kubectl context..." -Type Info
    
    # Minikube automatically sets context, but lets verify
    $context = kubectl config current-context 2>&1
    
    if ($context -eq "minikube") {
        Write-Status "kubectl context set to minikube" -Type Success
        return $true
    }
    
    # Try to set context manually
    $null = kubectl config use-context minikube 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "kubectl context switched to minikube" -Type Success
        return $true
    }
    
    Write-Status "Failed to set kubectl context" -Type Error
    return $false
}

function Test-ClusterReady {
    Write-Status "Verifying cluster is ready..." -Type Info
    
    # Wait for cluster to be ready
    $maxRetries = 30
    $retryCount = 0
    
    while ($retryCount -lt $maxRetries) {
        $status = minikube status --format="{{.Host}}" 2>&1
        
        if ($status -eq "Running") {
            break
        }
        
        $retryCount++
        Write-Host "  Waiting for cluster... ($retryCount/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 5
    }
    
    if ($retryCount -ge $maxRetries) {
        Write-Status "Cluster failed to become ready in time" -Type Error
        return $false
    }
    
    Write-Status "Cluster is ready" -Type Success
    return $true
}

function Test-KubectlCommands {
    Write-Status "Testing kubectl commands..." -Type Info
    
    $tests = @(
        @{ Command = "kubectl cluster-info"; Description = "Cluster info" },
        @{ Command = "kubectl get nodes"; Description = "Get nodes" },
        @{ Command = "kubectl get namespaces"; Description = "Get namespaces" },
        @{ Command = "kubectl get pods -A"; Description = "Get all pods" }
    )
    
    $allPassed = $true
    
    foreach ($test in $tests) {
        Write-Host "  Testing: $($test.Description)" -ForegroundColor Gray
        
        $null = Invoke-Expression $test.Command 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    + $($test.Description) - OK" -ForegroundColor Green
        }
        else {
            Write-Host "    - $($test.Description) - FAILED" -ForegroundColor Red
            $allPassed = $false
        }
    }
    
    if ($allPassed) {
        Write-Status "All kubectl tests passed" -Type Success
    }
    else {
        Write-Status "Some kubectl tests failed" -Type Warning
    }
    
    return $allPassed
}

function Show-ClusterInfo {
    Write-Header "Cluster Information"
    
    Write-Host "Minikube Status:" -ForegroundColor Cyan
    minikube status
    
    Write-Host ""
    Write-Host "Kubernetes Version:" -ForegroundColor Cyan
    $null = kubectl version --short 2>$null
    
    Write-Host ""
    Write-Host "Nodes:" -ForegroundColor Cyan
    kubectl get nodes -o wide
    
    Write-Host ""
    Write-Host "Enabled Addons:" -ForegroundColor Cyan
    minikube addons list | Select-String "enabled"
    
    Write-Host ""
    Write-Host "Useful Commands:" -ForegroundColor Cyan
    Write-Host "  minikube dashboard     - Open Kubernetes Dashboard" -ForegroundColor Gray
    Write-Host "  minikube ssh           - SSH into Minikube VM" -ForegroundColor Gray
    Write-Host "  minikube stop          - Stop the cluster" -ForegroundColor Gray
    Write-Host "  minikube delete        - Delete the cluster" -ForegroundColor Gray
    Write-Host "  kubectl get pods -A    - List all pods" -ForegroundColor Gray
}

# ============================================================================
# Main Script Execution
# ============================================================================

Write-Header "Minikube Setup for RAG System"
Write-Host "This script will set up a local Kubernetes cluster using Minikube."
Write-Host ""

# Step 1: Check prerequisites
Write-Header "Step 1: Checking Prerequisites"

# Check for Docker
if (-not (Test-DockerRunning)) {
    Write-Status "Docker Desktop is not running. Please start it first." -Type Error
    Write-Host ""
    Write-Host "To start Docker Desktop:" -ForegroundColor Yellow
    Write-Host "  1. Open Docker Desktop from Start Menu" -ForegroundColor Gray
    Write-Host "  2. Wait for it to fully start (system tray icon turns green)" -ForegroundColor Gray
    Write-Host "  3. Run this script again" -ForegroundColor Gray
    Write-Host ""
    exit 1
}
Write-Status "Docker Desktop is running" -Type Success

# Check for Minikube
$minikubeInstalled = Get-Command minikube -ErrorAction SilentlyContinue
if (-not $minikubeInstalled) {
    Write-Status "Minikube is not installed" -Type Warning
    
    $installMinikube = Read-Host "Would you like to install Minikube now? (Y/n)"
    if ($installMinikube -ne "n" -and $installMinikube -ne "N") {
        if (-not (Install-Minikube)) {
            Write-Status "Please install Minikube manually and run this script again" -Type Error
            exit 1
        }
        # Re-check after installation
        $minikubeInstalled = Get-Command minikube -ErrorAction SilentlyContinue
        if (-not $minikubeInstalled) {
            Write-Status "Minikube installation could not be verified. Please restart PowerShell and run again." -Type Error
            exit 1
        }
    }
    else {
        Write-Status "Minikube is required. Exiting." -Type Error
        exit 1
    }
}
else {
    $minikubeVersion = minikube version --short 2>$null
    Write-Status "Minikube is installed ($minikubeVersion)" -Type Success
}

# Check for kubectl
$kubectlInstalled = Get-Command kubectl -ErrorAction SilentlyContinue
if (-not $kubectlInstalled) {
    Write-Status "kubectl is not installed. It will be configured by Minikube." -Type Warning
}
else {
    $kubectlVersion = kubectl version --client --short 2>$null
    Write-Status "kubectl is installed ($kubectlVersion)" -Type Success
}

# Check for Helm
$helmInstalled = Get-Command helm -ErrorAction SilentlyContinue
if (-not $helmInstalled) {
    Write-Status "Helm is not installed" -Type Warning
    
    $installHelm = Read-Host "Would you like to install Helm now? (Y/n)"
    if ($installHelm -ne "n" -and $installHelm -ne "N") {
        Install-Helm
    }
}
else {
    $helmVersion = helm version --short 2>$null
    Write-Status "Helm is installed ($helmVersion)" -Type Success
}

# Step 2: Check existing Minikube status
Write-Header "Step 2: Checking Existing Cluster"

$existingStatus = minikube status 2>&1
if ($existingStatus -match "Running") {
    Write-Status "Existing Minikube cluster is running" -Type Info
    
    if (-not $Force) {
        $recreate = Read-Host "Would you like to delete and recreate it? (y/N)"
        if ($recreate -eq "y" -or $recreate -eq "Y") {
            Write-Status "Deleting existing cluster..." -Type Info
            minikube delete
        }
        else {
            Write-Status "Using existing cluster" -Type Info
            Set-KubectlContext
            Show-ClusterInfo
            exit 0
        }
    }
    else {
        Write-Status "Force flag set - deleting existing cluster..." -Type Info
        minikube delete
    }
}

# Step 3: Start Minikube
Write-Header "Step 3: Starting Minikube Cluster"

if (-not (Start-MinikubeCluster -CPUs $CPUs -Memory $Memory -DiskSize $DiskSize -Driver $Driver)) {
    Write-Status "Failed to start Minikube. Check the error messages above." -Type Error
    Write-Host ""
    Write-Host "Common solutions:" -ForegroundColor Yellow
    Write-Host "  1. Ensure Docker Desktop is running and healthy" -ForegroundColor Gray
    Write-Host "  2. Try: minikube delete --all --purge" -ForegroundColor Gray
    Write-Host "  3. Restart Docker Desktop" -ForegroundColor Gray
    Write-Host "  4. Check available disk space and RAM" -ForegroundColor Gray
    exit 1
}

# Step 4: Wait for cluster to be ready
Write-Header "Step 4: Waiting for Cluster"

if (-not (Test-ClusterReady)) {
    Write-Status "Cluster did not become ready. Please check minikube logs." -Type Error
    Write-Host "  Run: minikube logs" -ForegroundColor Gray
    exit 1
}

# Step 5: Enable addons
Write-Header "Step 5: Enabling Addons"
Enable-MinikubeAddons

# Step 6: Configure kubectl
Write-Header "Step 6: Configuring kubectl"
Set-KubectlContext

# Step 7: Test kubectl commands
Write-Header "Step 7: Testing Cluster"
Test-KubectlCommands

# Step 8: Show final status
Write-Header "Setup Complete!"
Show-ClusterInfo

Write-Host ""
Write-Status "Minikube is ready for RAG system deployment!" -Type Success
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run the verification script: .\scripts\verify-environment.ps1" -ForegroundColor Gray
Write-Host "  2. Deploy your application using Helm or kubectl" -ForegroundColor Gray
Write-Host "  3. Access the dashboard: minikube dashboard" -ForegroundColor Gray
Write-Host ""
