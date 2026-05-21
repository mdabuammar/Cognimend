#!/usr/bin/env pwsh
# Quick Docker Compose Test Script

Write-Host "Testing Docker Compose Setup" -ForegroundColor Cyan

# Check Docker
try {
    docker --version | Out-Null
    Write-Host "✅ Docker is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not found" -ForegroundColor Red
    exit 1
}

# Check Docker Compose
try {
    docker-compose --version | Out-Null
    Write-Host "✅ Docker Compose is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose not found" -ForegroundColor Red
    exit 1
}

# Check .env file
if (Test-Path ".env") {
    Write-Host "✅ .env file exists" -ForegroundColor Green
} else {
    Write-Host "❌ .env file missing" -ForegroundColor Red
    exit 1
}

# Check Dockerfiles
$dockerfiles = @(
    "services/upload/Dockerfile",
    "services/query/Dockerfile",
    "services/telemetry/Dockerfile",
    "services/drift_detector/Dockerfile",
    "services/controller/Dockerfile",
    "services/evaluation/Dockerfile"
)

$allFound = $true
foreach ($dockerfile in $dockerfiles) {
    if (Test-Path $dockerfile) {
        Write-Host "✅ $dockerfile exists" -ForegroundColor Green
    } else {
        Write-Host "❌ $dockerfile missing" -ForegroundColor Red
        $allFound = $false
    }
}

if ($allFound) {
    Write-Host ""
    Write-Host "All checks passed! Ready to run:" -ForegroundColor Cyan
    Write-Host "  docker-compose build" -ForegroundColor Gray
    Write-Host "  docker-compose up -d" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To start the complete test:" -ForegroundColor Cyan
    Write-Host "  1. Run: docker-compose build" -ForegroundColor Gray
    Write-Host "  2. Run: docker-compose up -d" -ForegroundColor Gray
    Write-Host "  3. Check logs: docker-compose logs -f" -ForegroundColor Gray
    Write-Host "  4. Verify health: curl http://localhost:8003/dashboard/stats" -ForegroundColor Gray
} else {
    exit 1
}
