Write-Host "Starting Cognimend RAG System on Localhost..." -ForegroundColor Green

# Check Docker Desktop
$dockerProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Write-Host "Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop first, then run this script again." -ForegroundColor Yellow
    exit 1
}

# Navigate to backend directory
$backendDir = Split-Path $PSScriptRoot -Parent
Set-Location -Path $backendDir

# Create .env if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    
    Write-Host "Enter your OpenRouter API key: " -ForegroundColor Cyan -NoNewline
    $apiKey = Read-Host
    (Get-Content ".env") -replace 'OPENROUTER_API_KEY=.*', "OPENROUTER_API_KEY=$apiKey" | Set-Content ".env"
    Write-Host ".env created with API key!" -ForegroundColor Green
}

# Clean up previous containers
Write-Host "Cleaning up previous containers..." -ForegroundColor Yellow
docker-compose down -v 2>$null

# Build images
Write-Host "Building Docker images..." -ForegroundColor Yellow
docker-compose build --no-cache

# Start services
Write-Host "Starting services..." -ForegroundColor Green
docker-compose up -d

# Wait for services to be healthy
Write-Host "Waiting for services to be ready (up to 5 minutes)..." -ForegroundColor Yellow
$timeout = 300
$startTime = Get-Date

do {
    $status = docker-compose ps --services --filter "health=healthy" 2>$null
    $healthyCount = ($status | Measure-Object).Count
    $elapsed = (Get-Date) - $startTime
    
    Write-Host "Waiting... $healthyCount/9 services healthy ($([math]::Round($elapsed.TotalSeconds))s)" -ForegroundColor Cyan
    
    Start-Sleep 10
} while ($healthyCount -lt 9 -and $elapsed.TotalSeconds -lt $timeout)

# Show status
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
docker-compose ps

# Test health endpoints
Write-Host ""
Write-Host "Testing health endpoints:" -ForegroundColor Cyan
$services = @("8001", "8002", "8003", "8004", "8005", "8006")
foreach ($port in $services) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -Method Get -TimeoutSec 5 -UseBasicParsing
        Write-Host "[OK] localhost:$port/health - OK" -ForegroundColor Green
    }
    catch {
        Write-Host "[X] localhost:$port/health - Failed" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "+========================================+" -ForegroundColor Green
Write-Host "|   RAG SYSTEM RUNNING ON LOCALHOST!    |" -ForegroundColor Green
Write-Host "+========================================+" -ForegroundColor Green
Write-Host ""

Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  Upload:     http://localhost:8001" -ForegroundColor White
Write-Host "  Query:      http://localhost:8002" -ForegroundColor White
Write-Host "  Telemetry:  http://localhost:8003" -ForegroundColor White
Write-Host "  Drift:      http://localhost:8004" -ForegroundColor White
Write-Host "  Controller: http://localhost:8005" -ForegroundColor White
Write-Host "  Evaluation: http://localhost:8006" -ForegroundColor White
Write-Host ""

Write-Host "API Docs:" -ForegroundColor Cyan
Write-Host "  -> http://localhost:8002/docs (Swagger UI)" -ForegroundColor White
Write-Host ""

Write-Host "Quick Test Commands:" -ForegroundColor Cyan
Write-Host '  Upload: curl -X POST http://localhost:8001/upload -F "file=@test.txt" -F "title=Test"' -ForegroundColor White
Write-Host '  Query:  curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d "{\"question\":\"What is this about?\"}"' -ForegroundColor White
Write-Host ""

Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  Logs:    docker-compose logs -f query-service" -ForegroundColor White
Write-Host "  Restart: docker-compose restart query-service" -ForegroundColor White
Write-Host "  Stop:    docker-compose down" -ForegroundColor White
Write-Host ""
