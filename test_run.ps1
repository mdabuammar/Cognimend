Write-Host "Upload Service Test" -ForegroundColor Cyan
Write-Host "=" * 60

$UPLOAD_URL = "http://localhost:8001/upload"
$TEST_FILE = "D:\Project\sample.txt"

Write-Host ""
Write-Host "TEST 1: Upload Document" -ForegroundColor Cyan
Write-Host "-" * 60
Write-Host "POST $UPLOAD_URL"
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri $UPLOAD_URL `
        -Method POST `
        -Form @{
            file = Get-Item -Path $TEST_FILE
            title = "Company Policy"
        } `
        -ErrorAction Stop
    
    $result = $response.Content | ConvertFrom-Json
    
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
    
    Write-Host ""
    Write-Host "=" * 60
    Write-Host "Upload test completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "Upload failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
