# =============================================================================
# DriftGuard Docker Build Script (PowerShell)
# =============================================================================
# Builds all microservice Docker images with proper tagging and optimization.
#
# Usage:
#   .\build-images.ps1                    # Build all with :latest tag
#   .\build-images.ps1 -Version v1.2.3    # Build all with specific version
#   .\build-images.ps1 -Version v1.2.3 -Service controller  # Build specific service
#
# =============================================================================

param(
    [string]$Version = "latest",
    [string]$Service = "all",
    [string]$Registry = "ghcr.io/driftguard",
    [switch]$Push
)

$ErrorActionPreference = "Stop"

# Configuration
$BuildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$VcsRef = git rev-parse --short HEAD 2>$null
if (-not $VcsRef) { $VcsRef = "unknown" }

# Services to build
$Services = @(
    @{ Name = "controller"; Port = 8005 },
    @{ Name = "query"; Port = 8002 },
    @{ Name = "upload"; Port = 8001 },
    @{ Name = "evaluation"; Port = 8003 },
    @{ Name = "drift_detector"; Port = 8004 },
    @{ Name = "telemetry"; Port = 8006 }
)

function Build-Service {
    param(
        [string]$ServiceName,
        [int]$Port
    )
    
    $Dockerfile = "services/$ServiceName/Dockerfile.optimized"
    $ImageName = "$Registry/${ServiceName}:$Version"
    
    Write-Host "Building $ServiceName..." -ForegroundColor Yellow
    
    if (-not (Test-Path $Dockerfile)) {
        Write-Host "Optimized Dockerfile not found, using standard Dockerfile" -ForegroundColor Yellow
        $Dockerfile = "services/$ServiceName/Dockerfile"
    }
    
    docker build `
        --file $Dockerfile `
        --tag $ImageName `
        --tag "$Registry/${ServiceName}:latest" `
        --build-arg BUILD_VERSION="$Version" `
        --build-arg BUILD_DATE="$BuildDate" `
        --build-arg VCS_REF="$VcsRef" `
        --label "org.opencontainers.image.created=$BuildDate" `
        --label "org.opencontainers.image.revision=$VcsRef" `
        --label "org.opencontainers.image.version=$Version" `
        .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build $ServiceName" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Built $ImageName" -ForegroundColor Green
    
    if ($Push) {
        Write-Host "Pushing $ServiceName..." -ForegroundColor Yellow
        docker push $ImageName
        docker push "$Registry/${ServiceName}:latest"
        Write-Host "✓ Pushed $ImageName" -ForegroundColor Green
    }
}

# Main execution
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "DriftGuard Docker Build" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Registry: $Registry"
Write-Host "Version: $Version"
Write-Host "Build Date: $BuildDate"
Write-Host "VCS Ref: $VcsRef"
Write-Host "==============================================" -ForegroundColor Cyan

Push-Location $PSScriptRoot

try {
    if ($Service -eq "all") {
        foreach ($svc in $Services) {
            Build-Service -ServiceName $svc.Name -Port $svc.Port
        }
    } else {
        $svc = $Services | Where-Object { $_.Name -eq $Service }
        if ($svc) {
            Build-Service -ServiceName $svc.Name -Port $svc.Port
        } else {
            Write-Host "Service '$Service' not found" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "Build Complete!" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Image Sizes:" -ForegroundColor Cyan
    docker images --filter "reference=$Registry/*:$Version" --format "table {{.Repository}}`t{{.Tag}}`t{{.Size}}"
}
finally {
    Pop-Location
}
