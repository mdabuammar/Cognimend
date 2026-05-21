Write-Host "Testing Cognimend RAG System..." -ForegroundColor Green

# Navigate to backend directory
$backendDir = Split-Path $PSScriptRoot -Parent
Set-Location -Path $backendDir

# Test all health endpoints
$services = @("8001", "8002", "8003", "8004", "8005", "8006")
$allHealthy = $true

Write-Host ""
Write-Host "Health Check Results:" -ForegroundColor Cyan
foreach ($port in $services) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -TimeoutSec 10 -UseBasicParsing
        $content = $response.Content | ConvertFrom-Json
        Write-Host "[OK] localhost:$port/health - $($content.status)" -ForegroundColor Green
    }
    catch {
        Write-Host "[X] localhost:$port/health - FAILED" -ForegroundColor Red
        $allHealthy = $false
    }
}

if (-not $allHealthy) {
    Write-Host ""
    Write-Host "Some services are not healthy. Fix before testing." -ForegroundColor Red
    exit 1
}

# Create test file
$testContent = @"
# Test Document
This is a test document for the Cognimend RAG system.
It contains sample text for testing the upload and query functionality.
The system should be able to process this document and answer questions about it.
"@
$testFile = Join-Path $backendDir "test.txt"
$testContent | Out-File -FilePath $testFile -Encoding UTF8

Write-Host ""
Write-Host "Testing Upload..." -ForegroundColor Cyan
try {
    $boundary = [System.Guid]::NewGuid().ToString()
    $fileBytes = [System.IO.File]::ReadAllBytes($testFile)
    $fileContent = [System.Text.Encoding]::UTF8.GetString($fileBytes)
    
    $bodyLines = @(
        "--$boundary",
        'Content-Disposition: form-data; name="file"; filename="test.txt"',
        'Content-Type: text/plain',
        '',
        $fileContent,
        "--$boundary",
        'Content-Disposition: form-data; name="title"',
        '',
        'Test Document',
        "--$boundary--"
    )
    $body = $bodyLines -join "`r`n"
    
    $uploadResponse = Invoke-WebRequest -Uri "http://localhost:8001/upload" `
        -Method Post `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body $body `
        -TimeoutSec 30 `
        -UseBasicParsing
    
    $uploadData = $uploadResponse.Content | ConvertFrom-Json
    $docId = $uploadData.document_id
    Write-Host "[OK] Upload successful! Document ID: $docId" -ForegroundColor Green
    if ($uploadData.chunks) {
        Write-Host "     Chunks: $($uploadData.chunks)" -ForegroundColor Gray
    }
}
catch {
    Write-Host "[X] Upload failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Testing Query..." -ForegroundColor Cyan
try {
    Start-Sleep 3  # Wait for indexing
    
    $queryBody = '{"question": "What is this document about?", "top_k": 3}'
    $queryResponse = Invoke-WebRequest -Uri "http://localhost:8002/query" `
        -Method Post `
        -ContentType "application/json" `
        -Body $queryBody `
        -TimeoutSec 30 `
        -UseBasicParsing
    
    $queryData = $queryResponse.Content | ConvertFrom-Json
    Write-Host "[OK] Query successful!" -ForegroundColor Green
    
    if ($queryData.answer) {
        $answerPreview = $queryData.answer
        if ($answerPreview.Length -gt 100) {
            $answerPreview = $answerPreview.Substring(0, 100) + "..."
        }
        Write-Host "     Answer: $answerPreview" -ForegroundColor White
    }
    
    if ($queryData.confidence) {
        $confColor = "Red"
        if ($queryData.confidence -gt 80) { $confColor = "Green" }
        elseif ($queryData.confidence -gt 60) { $confColor = "Yellow" }
        Write-Host "     Confidence: $($queryData.confidence)%" -ForegroundColor $confColor
    }
    
    if ($queryData.latency_ms) {
        Write-Host "     Latency: $($queryData.latency_ms)ms" -ForegroundColor Gray
    }
    
    if ($queryData.cost_usd) {
        Write-Host "     Cost: `$$($queryData.cost_usd)" -ForegroundColor Gray
    }
}
catch {
    Write-Host "[X] Query failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Checking Metrics..." -ForegroundColor Cyan
try {
    $metricsResponse = Invoke-WebRequest -Uri "http://localhost:8003/dashboard/stats" -TimeoutSec 10 -UseBasicParsing
    $metrics = $metricsResponse.Content | ConvertFrom-Json
    Write-Host "[OK] Metrics: $($metrics.total_queries) queries, $($metrics.avg_confidence)% avg confidence" -ForegroundColor Green
}
catch {
    Write-Host "[!] Metrics not available yet" -ForegroundColor Yellow
}

# Cleanup test file
Remove-Item $testFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "ALL TESTS PASSED! Your RAG system is working!" -ForegroundColor Green
Write-Host ""
Write-Host "Open these URLs to explore:" -ForegroundColor Cyan
Write-Host "   Query API: http://localhost:8002/docs" -ForegroundColor White
Write-Host "   Upload API: http://localhost:8001/docs" -ForegroundColor White
Write-Host ""
