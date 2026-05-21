# Simple PowerShell test script
Write-Host "Starting services..." -ForegroundColor Green

# Start upload service
Write-Host "Starting upload service on port 8001..." -ForegroundColor Cyan
Start-Process python -ArgumentList "D:\Project\backend\services\upload\main.py" -NoNewWindow

# Start query service  
Write-Host "Starting query service on port 8002..." -ForegroundColor Cyan
Start-Process python -ArgumentList "D:\Project\backend\services\query\main.py" -NoNewWindow

# Wait for services to start
Write-Host "Waiting 5 seconds for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Test upload endpoint
Write-Host "`nTest 1: Upload Service (port 8001)" -ForegroundColor Green
$uploadTest = curl.exe -s http://localhost:8001/health 2>&1
Write-Host $uploadTest

# Test query endpoint
Write-Host "`nTest 2: Query Service (port 8002)" -ForegroundColor Green
$queryTest = curl.exe -s http://localhost:8002/health 2>&1
Write-Host $queryTest

# Test metrics
Write-Host "`nTest 3: Metrics Endpoint" -ForegroundColor Green
$metricsTest = curl.exe -s http://localhost:8002/metrics 2>&1
Write-Host $metricsTest

Write-Host "`nAll tests completed!" -ForegroundColor Cyan
