#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test the Upload API endpoint
#>

Write-Host "🧪 Upload Service Test" -ForegroundColor Cyan
Write-Host "=" * 60

$UPLOAD_URL = "http://localhost:8001/upload"
$TEST_FILE = "D:\Project\sample.pdf"

# Create sample PDF if needed
if (-not (Test-Path $TEST_FILE)) {
    Write-Host "📝 Creating sample PDF..."
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
    Write-Host "✅ Sample PDF created" -ForegroundColor Green
}

Write-Host "`n📤 TEST 1: Upload Document" -ForegroundColor Cyan
Write-Host "-" * 60
Write-Host "POST $UPLOAD_URL"
Write-Host "File: sample.pdf"
Write-Host "Title: Company Policy`n"

try {
    $response = Invoke-WebRequest -Uri $UPLOAD_URL `
        -Method POST `
        -Form @{
            file = Get-Item -Path $TEST_FILE
            title = "Company Policy"
        } `
        -ErrorAction Stop
    
    $result = $response.Content | ConvertFrom-Json
    
    Write-Host "✅ Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "`n Response:" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
    
    Write-Host "`n"
    Write-Host "=" * 60
    Write-Host "✅ Upload test completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "❌ Upload failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}
