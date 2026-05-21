# Local Security Audit Script
# Runs pip-audit on all requirements.txt files

param(
    [switch]$Fix,
    [switch]$Json,
    [string]$Output = "audit-report.txt"
)

$ErrorActionPreference = "Stop"

Write-Host "🔒 Running Security Audit..." -ForegroundColor Cyan
Write-Host "=" * 50

# Check for pip-audit
$hasPipAudit = Get-Command pip-audit -ErrorAction SilentlyContinue
if (-not $hasPipAudit) {
    Write-Host "Installing pip-audit..." -ForegroundColor Yellow
    pip install pip-audit
}

$services = @(
    @{Name="backend-root"; Path="."},
    @{Name="upload"; Path="services/upload"},
    @{Name="query"; Path="services/query"},
    @{Name="controller"; Path="services/controller"},
    @{Name="evaluation"; Path="services/evaluation"},
    @{Name="drift_detector"; Path="services/drift_detector"},
    @{Name="telemetry"; Path="services/telemetry"}
)

$totalVulns = 0
$report = @()

foreach ($svc in $services) {
    $reqFile = Join-Path $svc.Path "requirements.txt"
    
    if (Test-Path $reqFile) {
        Write-Host "`n📦 Scanning $($svc.Name)..." -ForegroundColor Yellow
        
        $args = @("-r", $reqFile, "--desc", "on")
        if ($Json) { $args += @("--format", "json") }
        if ($Fix) { $args += "--fix" }
        
        try {
            $result = pip-audit @args 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ No vulnerabilities found" -ForegroundColor Green
                $report += "[$($svc.Name)] ✅ No vulnerabilities"
            } else {
                Write-Host "  ⚠️  Vulnerabilities detected:" -ForegroundColor Red
                $result | ForEach-Object { Write-Host "     $_" -ForegroundColor Red }
                $totalVulns++
                $report += "[$($svc.Name)] ⚠️ VULNERABLE"
                $report += $result
            }
        } catch {
            Write-Host "  ❌ Error scanning: $_" -ForegroundColor Red
        }
    }
}

Write-Host "`n" + "=" * 50
Write-Host "📊 AUDIT SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 50

if ($totalVulns -eq 0) {
    Write-Host "✅ All services passed security audit!" -ForegroundColor Green
} else {
    Write-Host "⚠️  $totalVulns service(s) have vulnerabilities" -ForegroundColor Red
    Write-Host "   Run with -Fix to attempt automatic remediation" -ForegroundColor Yellow
}

# Save report
$report | Out-File -FilePath $Output -Encoding UTF8
Write-Host "`n📝 Report saved to: $Output" -ForegroundColor Cyan

exit $totalVulns
