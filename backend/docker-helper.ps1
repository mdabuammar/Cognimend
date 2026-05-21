# Docker Helper Script
# Adds Docker to PATH for this session and provides helper functions

# Add Docker to PATH
$dockerPath = "C:\Program Files\Docker\Docker\resources\bin"
if ($env:PATH -notlike "*$dockerPath*") {
    $env:PATH += ";$dockerPath"
    Write-Host "✅ Docker added to PATH for this session" -ForegroundColor Green
}

# Helper function to check containers
function Show-Containers {
    docker ps
}

# Helper function to start services
function Start-Services {
    Write-Host "Starting Docker services..." -ForegroundColor Yellow
    docker compose up -d
    Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    docker ps
}

# Helper function to stop services
function Stop-Services {
    Write-Host "Stopping Docker services..." -ForegroundColor Yellow
    docker compose down
}

# Helper function to view logs
function Show-Logs {
    param([string]$Service = "")
    if ($Service) {
        docker compose logs -f $Service
    } else {
        docker compose logs -f
    }
}

Write-Host ""
Write-Host "Docker Helper Loaded!" -ForegroundColor Cyan
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  Show-Containers  - Show running containers" -ForegroundColor White
Write-Host "  Start-Services   - Start all Docker services" -ForegroundColor White
Write-Host "  Stop-Services    - Stop all Docker services" -ForegroundColor White
Write-Host "  Show-Logs        - View service logs (optionally: Show-Logs postgres)" -ForegroundColor White
Write-Host ""
