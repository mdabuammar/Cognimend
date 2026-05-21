# Generate Lockfile Script
# Uses uv (preferred) or pip-tools to create reproducible requirements.lock

param(
    [switch]$UsePipTools,
    [switch]$AllServices,
    [string]$Service
)

$ErrorActionPreference = "Stop"

Write-Host "🔒 Generating dependency lockfiles..." -ForegroundColor Cyan

# Check for uv
$hasUv = Get-Command uv -ErrorAction SilentlyContinue

if (-not $UsePipTools -and $hasUv) {
    Write-Host "✓ Using uv (fast, modern package manager)" -ForegroundColor Green
    
    # Generate lockfile for root
    Write-Host "`n📦 Generating root lockfile..." -ForegroundColor Yellow
    uv pip compile requirements.txt -o requirements.lock --generate-hashes
    
    if ($AllServices -or $Service) {
        $services = if ($Service) { @($Service) } else {
            @("upload", "query", "controller", "evaluation", "drift_detector", "telemetry")
        }
        
        foreach ($svc in $services) {
            $svcPath = "services/$svc"
            if (Test-Path "$svcPath/requirements.txt") {
                Write-Host "📦 Generating lockfile for $svc..." -ForegroundColor Yellow
                Push-Location $svcPath
                uv pip compile requirements.txt -o requirements.lock --generate-hashes
                Pop-Location
            }
        }
    }
} else {
    Write-Host "Using pip-tools (install with: pip install pip-tools)" -ForegroundColor Yellow
    
    # Check for pip-compile
    $hasPipCompile = Get-Command pip-compile -ErrorAction SilentlyContinue
    if (-not $hasPipCompile) {
        Write-Host "Installing pip-tools..." -ForegroundColor Yellow
        pip install pip-tools
    }
    
    # Generate lockfile for root
    Write-Host "`n📦 Generating root lockfile..." -ForegroundColor Yellow
    pip-compile requirements.txt -o requirements.lock --generate-hashes --resolver=backtracking
    
    if ($AllServices -or $Service) {
        $services = if ($Service) { @($Service) } else {
            @("upload", "query", "controller", "evaluation", "drift_detector", "telemetry")
        }
        
        foreach ($svc in $services) {
            $svcPath = "services/$svc"
            if (Test-Path "$svcPath/requirements.txt") {
                Write-Host "📦 Generating lockfile for $svc..." -ForegroundColor Yellow
                Push-Location $svcPath
                pip-compile requirements.txt -o requirements.lock --generate-hashes --resolver=backtracking
                Pop-Location
            }
        }
    }
}

Write-Host "`n✅ Lockfiles generated successfully!" -ForegroundColor Green
Write-Host @"

📝 Usage:
  - Install from lockfile: pip install -r requirements.lock
  - With uv:               uv pip sync requirements.lock
  
🔄 Regenerate when:
  - Adding/removing dependencies
  - Updating version constraints
  - Before deploying to production
"@ -ForegroundColor Cyan
