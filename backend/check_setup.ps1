# Setup Checker Script
Write-Host "=== Cognimend Setup Checker ===" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerInstalled) {
    Write-Host "✅ Docker is installed" -ForegroundColor Green
    docker --version
} else {
    Write-Host "❌ Docker is NOT installed" -ForegroundColor Red
    Write-Host "   → Download from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
}

Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonInstalled = Get-Command python -ErrorAction SilentlyContinue
if ($pythonInstalled) {
    Write-Host "✅ Python is installed" -ForegroundColor Green
    python --version
} else {
    Write-Host "❌ Python is NOT installed" -ForegroundColor Red
    Write-Host "   → Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
}

Write-Host ""

# Check .env file
Write-Host "Checking .env file..." -ForegroundColor Yellow
if (Test-Path ".\backend\.env") {
    Write-Host "✅ .env file exists" -ForegroundColor Green
    
    # Check if OpenAI key is set (without showing the key)
    $envContent = Get-Content ".\backend\.env" -ErrorAction SilentlyContinue
    $hasKey = $envContent | Select-String -Pattern "OPENAI_API_KEY=" -Quiet
    if ($hasKey) {
        Write-Host "✅ OpenAI API key appears to be set" -ForegroundColor Green
    } else {
        Write-Host "⚠️  OpenAI API key needs to be updated in .env" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ .env file NOT found" -ForegroundColor Red
}

Write-Host ""

# Check service files
Write-Host "Checking service files..." -ForegroundColor Yellow
$uploadExists = Test-Path ".\backend\services\upload\main.py"
$queryExists = Test-Path ".\backend\services\query\main.py"

if ($uploadExists) {
    Write-Host "✅ Upload service found" -ForegroundColor Green
} else {
    Write-Host "❌ Upload service NOT found" -ForegroundColor Red
}

if ($queryExists) {
    Write-Host "✅ Query service found" -ForegroundColor Green
} else {
    Write-Host "❌ Query service NOT found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Install Docker Desktop if not installed" -ForegroundColor White
Write-Host "2. Update OPENAI_API_KEY in backend/.env" -ForegroundColor White
Write-Host "3. Run: cd backend && docker compose up -d" -ForegroundColor White
Write-Host "4. Start upload service: cd services/upload && python main.py" -ForegroundColor White
Write-Host "5. Start query service: cd services/query && python main.py" -ForegroundColor White
