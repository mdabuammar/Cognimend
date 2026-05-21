#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test script for Upload and Query API endpoints
.DESCRIPTION
    This script tests the upload and query services with sample data
#>

# Configuration
$UPLOAD_URL = "http://localhost:8001/upload"
$QUERY_URL = "http://localhost:8002/query"
$TEST_FILE = "D:\Project\sample.pdf"

Write-Host "🧪 API Test Suite" -ForegroundColor Cyan
Write-Host "=" * 60

# Check if services are running
Write-Host "`n📋 Checking service availability..."
try {
    $null = Invoke-WebRequest -Uri "http://localhost:8001/docs" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Upload Service (8001) is running" -ForegroundColor Green
}
catch {
    Write-Host "❌ Upload Service (8001) is NOT running" -ForegroundColor Red
    Write-Host "   Start it with: python -m uvicorn main:app --port 8001 (in backend/services/upload)"
    exit 1
}

try {
    $null = Invoke-WebRequest -Uri "http://localhost:8002/docs" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Query Service (8002) is running" -ForegroundColor Green
}
catch {
    Write-Host "❌ Query Service (8002) is NOT running" -ForegroundColor Red
    Write-Host "   Start it with: python -m uvicorn main:app --port 8002 (in backend/services/query)"
    exit 1
}

# Create a sample PDF if it doesn't exist
if (-not (Test-Path $TEST_FILE)) {
    Write-Host "`n📝 Creating sample PDF file..."
    # Create a minimal PDF file
    $pdfContent = @"
%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 77 >>
stream
BT
/F1 12 Tf
100 700 Td
(This is a sample PDF for testing) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000273 00000 n
0000000362 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
489
%%EOF
"@
    Set-Content -Path $TEST_FILE -Value $pdfContent -Encoding UTF8
    Write-Host "✅ Sample PDF created at $TEST_FILE" -ForegroundColor Green
}

# Test 1: Upload a Document
Write-Host "`n" 
Write-Host "📤 TEST 1: Upload a Document" -ForegroundColor Cyan
Write-Host "-" * 60
Write-Host "Endpoint: POST $UPLOAD_URL"
Write-Host "File: $TEST_FILE"
Write-Host "Title: Company Policy`n"

try {
    $response = Invoke-WebRequest -Uri $UPLOAD_URL `
        -Method POST `
        -Form @{
            file = Get-Item -Path $TEST_FILE
            title = "Company Policy"
        } `
        -ErrorAction Stop
    
    Write-Host "✅ Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Response:`n$($response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10)" -ForegroundColor Green
    
    # Extract document ID for query test
    $uploadResponse = $response.Content | ConvertFrom-Json
    $docId = $uploadResponse.document_id
}
catch {
    Write-Host "❌ Upload failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Response: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Query Documents
Write-Host "`n"
Write-Host "❓ TEST 2: Query Documents" -ForegroundColor Cyan
Write-Host "-" * 60
Write-Host "Endpoint: POST $QUERY_URL"
Write-Host "Query: What is the leave policy?`n"

try {
    $queryPayload = @{
        question = "What is the leave policy?"
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri $QUERY_URL `
        -Method POST `
        -ContentType "application/json" `
        -Body $queryPayload `
        -ErrorAction Stop
    
    Write-Host "✅ Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Response:`n$($response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10)" -ForegroundColor Green
}
catch {
    Write-Host "❌ Query failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Response: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n"
Write-Host "=" * 60
Write-Host "✅ All tests completed!" -ForegroundColor Green
