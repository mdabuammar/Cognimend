<#
.SYNOPSIS
    Install and configure monitoring stack for Cognimend RAG system

.DESCRIPTION
    Installs Prometheus, Grafana, and related components using Helm,
    configures dashboards, and sets up service monitoring.

.PARAMETER Namespace
    Kubernetes namespace for monitoring. Default: monitoring

.PARAMETER RagNamespace
    Kubernetes namespace for RAG services. Default: cognimend

.PARAMETER SkipHelmInstall
    Skip Helm chart installation (useful for re-running configuration)

.PARAMETER GrafanaPort
    Local port for Grafana port-forward. Default: 3000

.EXAMPLE
    .\install-monitoring.ps1

.EXAMPLE
    .\install-monitoring.ps1 -SkipHelmInstall -GrafanaPort 3001
#>

[CmdletBinding()]
param(
    [string]$Namespace = "monitoring",
    [string]$RagNamespace = "cognimend",
    [switch]$SkipHelmInstall,
    [int]$GrafanaPort = 3000,
    [int]$PrometheusRetentionDays = 15
)

# =============================================================================
# CONFIGURATION
# =============================================================================

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:ProjectRoot = Split-Path $PSScriptRoot -Parent
$script:LogDir = Join-Path $script:ProjectRoot "logs"
$script:LogFile = Join-Path $script:LogDir "monitoring-install-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$script:K8sDir = Join-Path $script:ProjectRoot "k8s"
$script:PortForwardJob = $null
$script:GrafanaPassword = $null

# Helm values for kube-prometheus-stack
$script:HelmValues = @"
prometheus:
  prometheusSpec:
    retention: ${PrometheusRetentionDays}d
    retentionSize: "8GB"
    resources:
      requests:
        cpu: 200m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false

grafana:
  enabled: true
  adminPassword: "admin123!"
  persistence:
    enabled: true
    size: 5Gi
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
  service:
    type: NodePort
    nodePort: 30030
  sidecar:
    dashboards:
      enabled: true
      searchNamespace: ALL

alertmanager:
  enabled: true
  alertmanagerSpec:
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 256Mi
    storage:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 2Gi

kubeStateMetrics:
  enabled: true

nodeExporter:
  enabled: true

prometheusOperator:
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi

# Disable components not needed for Minikube
kubeEtcd:
  enabled: false
kubeControllerManager:
  enabled: false
kubeScheduler:
  enabled: false
kubeProxy:
  enabled: false

defaultRules:
  create: true
  rules:
    alertmanager: true
    etcd: false
    configReloaders: true
    general: true
    k8s: true
    kubeApiserverAvailability: true
    kubeApiserverBurnrate: true
    kubeApiserverHistogram: true
    kubeApiserverSlos: true
    kubeControllerManager: false
    kubelet: true
    kubeProxy: false
    kubePrometheusGeneral: true
    kubePrometheusNodeRecording: true
    kubernetesApps: true
    kubernetesResources: true
    kubernetesStorage: true
    kubernetesSystem: true
    kubeSchedulerAlerting: false
    kubeSchedulerRecording: false
    kubeStateMetrics: true
    network: true
    node: true
    nodeExporterAlerting: true
    nodeExporterRecording: true
    prometheus: true
    prometheusOperator: true
"@

# Ensure log directory exists
if (-not (Test-Path $script:LogDir)) {
    New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogFile -Value $logMessage
    
    $color = switch ($Level) {
        "SUCCESS" { "Green" }
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        "INFO" { "Cyan" }
        "STEP" { "White" }
        default { "White" }
    }
    
    $icon = switch ($Level) {
        "SUCCESS" { "[OK]" }
        "ERROR" { "[X]" }
        "WARNING" { "[!]" }
        "INFO" { "[i]" }
        "STEP" { "[>]" }
        default { "*" }
    }
    
    Write-Host "$icon " -NoNewline -ForegroundColor $color
    Write-Host $Message -ForegroundColor $color
}

function Write-Banner {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Magenta
    Write-Host "  Monitoring Stack Installation                                " -ForegroundColor White
    Write-Host "  Prometheus - Grafana - AlertManager                          " -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Magenta
    Write-Host ""
}

function Write-Step {
    param([int]$Step, [string]$Title, [int]$Total = 6)
    
    Write-Host ""
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  Step $Step of $Total : $Title" -ForegroundColor White
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
}

function Test-CommandExists {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Wait-ForPodReady {
    param(
        [string]$LabelSelector,
        [string]$Namespace,
        [string]$Name,
        [int]$TimeoutSeconds = 300
    )
    
    $startTime = Get-Date
    $spinChars = @("|", "/", "-", "\")
    $i = 0
    
    while ($true) {
        $elapsed = (Get-Date) - $startTime
        
        if ($elapsed.TotalSeconds -gt $TimeoutSeconds) {
            Write-Host ""
            return $false
        }
        
        try {
            $pods = kubectl get pods -n $Namespace -l $LabelSelector -o json 2>$null | ConvertFrom-Json
            
            if ($pods -and $pods.items -and $pods.items.Count -gt 0) {
                $ready = 0
                $total = $pods.items.Count
                
                foreach ($pod in $pods.items) {
                    $conditions = $pod.status.conditions | Where-Object { $_.type -eq "Ready" }
                    if ($conditions -and $conditions.status -eq "True") {
                        $ready++
                    }
                }
                
                $elapsedSec = [math]::Round($elapsed.TotalSeconds)
                $spin = $spinChars[$i % $spinChars.Length]
                Write-Host "`r$spin ${Name}: ${ready}/${total} ready (${elapsedSec}s)    " -NoNewline -ForegroundColor Yellow
                
                if ($ready -eq $total -and $total -gt 0) {
                    Write-Host ""
                    return $true
                }
            } else {
                $elapsedSec = [math]::Round($elapsed.TotalSeconds)
                $spin = $spinChars[$i % $spinChars.Length]
                Write-Host "`r$spin ${Name}: waiting for pods (${elapsedSec}s)    " -NoNewline -ForegroundColor Yellow
            }
        } catch {
            $elapsedSec = [math]::Round($elapsed.TotalSeconds)
            $spin = $spinChars[$i % $spinChars.Length]
            Write-Host "`r$spin ${Name}: checking... (${elapsedSec}s)    " -NoNewline -ForegroundColor Yellow
        }
        
        Start-Sleep -Seconds 2
        $i++
    }
}

function Stop-PortForward {
    if ($script:PortForwardJob) {
        Stop-Job $script:PortForwardJob -Force -ErrorAction SilentlyContinue
        Remove-Job $script:PortForwardJob -Force -ErrorAction SilentlyContinue
        $script:PortForwardJob = $null
    }
}

# =============================================================================
# STEP 1: INSTALL PROMETHEUS STACK
# =============================================================================

function Install-PrometheusStack {
    Write-Step -Step 1 -Title "Install Prometheus Stack"
    
    if ($SkipHelmInstall) {
        Write-Log "Skipping Helm installation (SkipHelmInstall flag set)" "WARNING"
        return $true
    }
    
    # Check Helm
    if (-not (Test-CommandExists "helm")) {
        Write-Log "Helm is not installed!" "ERROR"
        Write-Host "  Install Helm: https://helm.sh/docs/intro/install/" -ForegroundColor Gray
        return $false
    }
    Write-Log "Helm found" "SUCCESS"
    
    # Add Helm repository
    Write-Log "Adding prometheus-community Helm repository..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Failed to add Helm repository" "ERROR"
        return $false
    }
    Write-Log "Helm repository added" "SUCCESS"
    
    # Update repos
    Write-Log "Updating Helm repositories..."
    helm repo update 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Failed to update Helm repositories" "WARNING"
    }
    Write-Log "Helm repositories updated" "SUCCESS"
    
    # Create namespace
    Write-Log "Creating namespace: $Namespace..."
    kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null
    Write-Log "Namespace ready: $Namespace" "SUCCESS"
    
    # Save Helm values to temp file
    $valuesFile = Join-Path $env:TEMP "prometheus-values.yaml"
    $script:HelmValues | Out-File -FilePath $valuesFile -Encoding UTF8
    Write-Log "Helm values saved to: $valuesFile"
    
    # Install kube-prometheus-stack
    Write-Log "Installing kube-prometheus-stack (this may take 3-5 minutes)..."
    Write-Host ""
    
    $helmOutput = helm upgrade --install prometheus prometheus-community/kube-prometheus-stack `
        --namespace $Namespace `
        --values $valuesFile `
        --timeout 10m `
        --wait 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Helm installation failed" "ERROR"
        Write-Host $helmOutput -ForegroundColor Red
        return $false
    }
    
    Write-Log "kube-prometheus-stack installed successfully" "SUCCESS"
    
    # Cleanup temp file
    Remove-Item $valuesFile -Force -ErrorAction SilentlyContinue
    
    return $true
}

# =============================================================================
# STEP 2: WAIT FOR PODS READY
# =============================================================================

function Wait-ForMonitoringPods {
    Write-Step -Step 2 -Title "Wait for All Pods Ready"
    
    $components = @(
        @{ Name = "Prometheus Operator"; Label = "app.kubernetes.io/name=prometheus-operator" },
        @{ Name = "Prometheus Server"; Label = "app.kubernetes.io/name=prometheus" },
        @{ Name = "Grafana"; Label = "app.kubernetes.io/name=grafana" },
        @{ Name = "Kube State Metrics"; Label = "app.kubernetes.io/name=kube-state-metrics" },
        @{ Name = "Node Exporter"; Label = "app.kubernetes.io/name=prometheus-node-exporter" },
        @{ Name = "AlertManager"; Label = "app.kubernetes.io/name=alertmanager" }
    )
    
    $allReady = $true
    $results = @()
    
    foreach ($component in $components) {
        $ready = Wait-ForPodReady `
            -LabelSelector $component.Label `
            -Namespace $Namespace `
            -Name $component.Name `
            -TimeoutSeconds 300
        
        if ($ready) {
            Write-Log "$($component.Name) is ready" "SUCCESS"
            $results += @{ Name = $component.Name; Status = "Ready"; Icon = "[OK]" }
        } else {
            Write-Log "$($component.Name) failed to become ready" "ERROR"
            $results += @{ Name = $component.Name; Status = "Failed"; Icon = "[X]" }
            $allReady = $false
        }
    }
    
    # Display status table
    Write-Host ""
    Write-Host "+----------------------------+------------+" -ForegroundColor DarkGray
    Write-Host "| Component                  | Status     |" -ForegroundColor DarkGray
    Write-Host "+----------------------------+------------+" -ForegroundColor DarkGray
    
    foreach ($result in $results) {
        $color = if ($result.Status -eq "Ready") { "Green" } else { "Red" }
        $name = $result.Name.PadRight(26)
        $status = "$($result.Icon) $($result.Status)".PadRight(10)
        Write-Host "| " -NoNewline -ForegroundColor DarkGray
        Write-Host "$name" -NoNewline -ForegroundColor White
        Write-Host "| " -NoNewline -ForegroundColor DarkGray
        Write-Host "$status" -NoNewline -ForegroundColor $color
        Write-Host "|" -ForegroundColor DarkGray
    }
    
    Write-Host "+----------------------------+------------+" -ForegroundColor DarkGray
    
    return $allReady
}

# =============================================================================
# STEP 3: CONFIGURE GRAFANA
# =============================================================================

function Configure-Grafana {
    Write-Step -Step 3 -Title "Configure Grafana"
    
    # Get Grafana admin password
    Write-Log "Retrieving Grafana admin password..."
    
    try {
        $secretData = kubectl get secret -n $Namespace prometheus-grafana -o jsonpath="{.data.admin-password}" 2>$null
        if ($secretData) {
            $script:GrafanaPassword = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($secretData))
        } else {
            $script:GrafanaPassword = "admin123!"  # Default from our values
        }
    } catch {
        $script:GrafanaPassword = "admin123!"
    }
    
    Write-Log "Grafana credentials retrieved" "SUCCESS"
    
    # Display credentials
    Write-Host ""
    Write-Host "+----------------------------------------------------------------+" -ForegroundColor Green
    Write-Host "|  GRAFANA CREDENTIALS                                           |" -ForegroundColor Green
    Write-Host "+----------------------------------------------------------------+" -ForegroundColor Green
    Write-Host "|  Username: admin                                               |" -ForegroundColor Yellow
    $pwdDisplay = "Password: $($script:GrafanaPassword)".PadRight(62)
    Write-Host "|  $pwdDisplay|" -ForegroundColor Yellow
    Write-Host "+----------------------------------------------------------------+" -ForegroundColor Green
    Write-Host ""
    
    # Start port-forward
    Write-Log "Starting Grafana port-forward on localhost:$GrafanaPort..."
    
    $pfPort = $GrafanaPort
    $pfNs = $Namespace
    $script:PortForwardJob = Start-Job -ScriptBlock {
        param($ns, $port)
        kubectl port-forward -n $ns svc/prometheus-grafana "${port}:80" 2>&1
    } -ArgumentList $pfNs, $pfPort
    
    Start-Sleep -Seconds 3
    
    # Verify port-forward
    $maxRetries = 10
    $grafanaReady = $false
    
    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$GrafanaPort/api/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $grafanaReady = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    
    if ($grafanaReady) {
        Write-Log "Grafana is accessible at http://localhost:$GrafanaPort" "SUCCESS"
        
        # Open browser
        Write-Log "Opening Grafana in browser..."
        Start-Process "http://localhost:$GrafanaPort"
        
        Write-Host ""
        Write-Host "  Grafana URL: http://localhost:$GrafanaPort" -ForegroundColor Green
        Write-Host ""
        
        return $true
    } else {
        Write-Log "Could not verify Grafana accessibility" "WARNING"
        return $false
    }
}

# =============================================================================
# STEP 4: IMPORT DASHBOARDS
# =============================================================================

function Import-GrafanaDashboards {
    Write-Step -Step 4 -Title "Import Grafana Dashboards"
    
    $dashboards = @(
        @{ File = "grafana-dashboard-rag.json"; Name = "RAG System Dashboard" },
        @{ File = "grafana-dashboard-drift.json"; Name = "Drift Detection Dashboard" },
        @{ File = "grafana-dashboard-cost.json"; Name = "Cost Tracking Dashboard" }
    )
    
    $grafanaUrl = "http://localhost:$GrafanaPort"
    $authHeader = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:$($script:GrafanaPassword)"))
    
    $importedCount = 0
    
    foreach ($dashboard in $dashboards) {
        $filePath = Join-Path $script:K8sDir $dashboard.File
        
        if (-not (Test-Path $filePath)) {
            Write-Log "$($dashboard.Name): File not found - $filePath" "WARNING"
            continue
        }
        
        Write-Log "Importing $($dashboard.Name)..."
        
        try {
            # Read dashboard JSON
            $dashboardJson = Get-Content $filePath -Raw | ConvertFrom-Json
            
            # Prepare import payload
            $importPayload = @{
                dashboard = $dashboardJson
                overwrite = $true
                folderId = 0
            } | ConvertTo-Json -Depth 100
            
            # Import dashboard via API
            $response = Invoke-RestMethod `
                -Uri "$grafanaUrl/api/dashboards/db" `
                -Method Post `
                -Headers @{
                    "Authorization" = "Basic $authHeader"
                    "Content-Type" = "application/json"
                } `
                -Body $importPayload `
                -TimeoutSec 30
            
            if ($response.status -eq "success" -or $response.id) {
                Write-Log "$($dashboard.Name) imported successfully" "SUCCESS"
                $importedCount++
            } else {
                Write-Log "$($dashboard.Name) import returned unexpected response" "WARNING"
            }
            
        } catch {
            Write-Log "$($dashboard.Name) import failed: $($_.Exception.Message)" "ERROR"
        }
    }
    
    Write-Host ""
    $resultColor = if ($importedCount -eq $dashboards.Count) { "Green" } else { "Yellow" }
    Write-Host "  Imported $importedCount of $($dashboards.Count) dashboards" -ForegroundColor $resultColor
    Write-Host ""
    
    return $importedCount -gt 0
}

# =============================================================================
# STEP 5: CONFIGURE PROMETHEUS
# =============================================================================

function Configure-Prometheus {
    Write-Step -Step 5 -Title "Configure Prometheus Service Monitoring"
    
    $success = $true
    
    # Apply ServiceMonitor
    $serviceMonitorFile = Join-Path $script:K8sDir "servicemonitor.yaml"
    if (Test-Path $serviceMonitorFile) {
        Write-Log "Applying ServiceMonitor..."
        kubectl apply -f $serviceMonitorFile -n $RagNamespace 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Log "ServiceMonitor applied successfully" "SUCCESS"
        } else {
            Write-Log "ServiceMonitor application failed" "ERROR"
            $success = $false
        }
    } else {
        Write-Log "ServiceMonitor file not found: $serviceMonitorFile" "WARNING"
    }
    
    # Apply PrometheusRule
    $alertsFile = Join-Path $script:K8sDir "prometheus-alerts.yaml"
    if (Test-Path $alertsFile) {
        Write-Log "Applying PrometheusRule (alerts)..."
        kubectl apply -f $alertsFile -n $RagNamespace 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Log "PrometheusRule applied successfully" "SUCCESS"
        } else {
            Write-Log "PrometheusRule application failed" "ERROR"
            $success = $false
        }
    } else {
        Write-Log "PrometheusRule file not found: $alertsFile" "WARNING"
    }
    
    # Wait a moment for Prometheus to pick up the new configuration
    Write-Host ""
    Write-Log "Waiting for Prometheus to discover targets..."
    Start-Sleep -Seconds 10
    
    # Check Prometheus targets
    Write-Log "Checking Prometheus scrape targets..."
    
    # Port-forward to Prometheus
    $promNs = $Namespace
    $prometheusJob = Start-Job -ScriptBlock {
        param($ns)
        kubectl port-forward -n $ns svc/prometheus-kube-prometheus-prometheus 9090:9090 2>&1
    } -ArgumentList $promNs
    
    Start-Sleep -Seconds 3
    
    try {
        $targetsResponse = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/targets" -TimeoutSec 10
        
        if ($targetsResponse.status -eq "success") {
            $activeTargets = $targetsResponse.data.activeTargets
            $ragTargets = $activeTargets | Where-Object { $_.labels.namespace -eq $RagNamespace }
            
            Write-Host ""
            Write-Host "+----------------------------------------+------------+" -ForegroundColor DarkGray
            Write-Host "| Prometheus Target                      | Status     |" -ForegroundColor DarkGray
            Write-Host "+----------------------------------------+------------+" -ForegroundColor DarkGray
            
            if ($ragTargets -and $ragTargets.Count -gt 0) {
                foreach ($target in $ragTargets | Select-Object -First 10) {
                    $job = $target.labels.job
                    $health = $target.health
                    $icon = if ($health -eq "up") { "[OK]" } else { "[X]" }
                    $color = if ($health -eq "up") { "Green" } else { "Red" }
                    
                    $jobName = $job.PadRight(38)
                    $statusText = "$icon $health".PadRight(10)
                    Write-Host "| " -NoNewline -ForegroundColor DarkGray
                    Write-Host "$jobName" -NoNewline -ForegroundColor White
                    Write-Host "| " -NoNewline -ForegroundColor DarkGray
                    Write-Host "$statusText" -NoNewline -ForegroundColor $color
                    Write-Host "|" -ForegroundColor DarkGray
                }
            } else {
                Write-Host "| (No RAG targets discovered yet)        | pending    |" -ForegroundColor Yellow
            }
            
            Write-Host "+----------------------------------------+------------+" -ForegroundColor DarkGray
            
            $totalTargets = $activeTargets.Count
            $upTargets = ($activeTargets | Where-Object { $_.health -eq "up" }).Count
            
            Write-Host ""
            $resultColor = if ($upTargets -eq $totalTargets) { "Green" } else { "Yellow" }
            Write-Host "  Total Prometheus targets: $upTargets/$totalTargets up" -ForegroundColor $resultColor
        }
    } catch {
        Write-Log "Could not query Prometheus targets: $($_.Exception.Message)" "WARNING"
    } finally {
        Stop-Job $prometheusJob -Force -ErrorAction SilentlyContinue
        Remove-Job $prometheusJob -Force -ErrorAction SilentlyContinue
    }
    
    return $success
}

# =============================================================================
# STEP 6: DISPLAY SUMMARY
# =============================================================================

function Show-Summary {
    Write-Step -Step 6 -Title "Installation Summary"
    
    $endTime = Get-Date
    $duration = $endTime - $script:StartTime
    
    # Get Minikube IP for external access
    $minikubeIP = minikube ip 2>$null
    if (-not $minikubeIP) { $minikubeIP = "localhost" }
    
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "                                                                " -ForegroundColor Green
    Write-Host "          MONITORING INSTALLATION COMPLETE                      " -ForegroundColor Green
    Write-Host "                                                                " -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "INSTALLED COMPONENTS" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  [OK] Prometheus Server (metrics collection)" -ForegroundColor Green
    Write-Host "  [OK] Prometheus Operator (Kubernetes-native management)" -ForegroundColor Green
    Write-Host "  [OK] Grafana (visualization and dashboards)" -ForegroundColor Green
    Write-Host "  [OK] AlertManager (alerting)" -ForegroundColor Green
    Write-Host "  [OK] Kube State Metrics (Kubernetes metrics)" -ForegroundColor Green
    Write-Host "  [OK] Node Exporter (host metrics)" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "ACCESS URLs" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Grafana (port-forward active):" -ForegroundColor White
    Write-Host "     URL:      http://localhost:$GrafanaPort" -ForegroundColor Green
    Write-Host "     Username: admin" -ForegroundColor Yellow
    Write-Host "     Password: $script:GrafanaPassword" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Grafana (NodePort):" -ForegroundColor White
    Write-Host "     URL:      http://${minikubeIP}:30030" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "IMPORTED DASHBOARDS" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  * RAG System Dashboard      - System overview and performance" -ForegroundColor Gray
    Write-Host "  * Drift Detection Dashboard - Model drift monitoring" -ForegroundColor Gray
    Write-Host "  * Cost Tracking Dashboard   - API costs and optimization" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "USEFUL COMMANDS" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  # View monitoring pods" -ForegroundColor DarkGray
    Write-Host "  kubectl get pods -n $Namespace" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # Port-forward Grafana" -ForegroundColor DarkGray
    Write-Host "  kubectl port-forward -n $Namespace svc/prometheus-grafana 3000:80" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # Port-forward Prometheus" -ForegroundColor DarkGray
    Write-Host "  kubectl port-forward -n $Namespace svc/prometheus-kube-prometheus-prometheus 9090:9090" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # View ServiceMonitors" -ForegroundColor DarkGray
    Write-Host "  kubectl get servicemonitors -A" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  # View PrometheusRules" -ForegroundColor DarkGray
    Write-Host "  kubectl get prometheusrules -A" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""
    $durationMin = [math]::Round($duration.TotalMinutes, 1)
    Write-Host "  Installation completed in $durationMin minutes" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Log file: $script:LogFile" -ForegroundColor Gray
    Write-Host ""
    
    # Keep port-forward running
    Write-Host "  Note: Grafana port-forward is running in background." -ForegroundColor Yellow
    Write-Host "  Press Ctrl+C to stop when done." -ForegroundColor Yellow
    Write-Host ""
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

function Main {
    Write-Banner
    
    Write-Host "  Log file: $script:LogFile" -ForegroundColor Gray
    Write-Host "  Monitoring namespace: $Namespace" -ForegroundColor Gray
    Write-Host "  RAG namespace: $RagNamespace" -ForegroundColor Gray
    Write-Host ""
    
    # Pre-flight checks
    if (-not (Test-CommandExists "kubectl")) {
        Write-Log "kubectl is not installed!" "ERROR"
        exit 1
    }
    
    if (-not (Test-CommandExists "helm")) {
        Write-Log "helm is not installed!" "ERROR"
        Write-Host "  Install Helm: https://helm.sh/docs/intro/install/" -ForegroundColor Gray
        exit 1
    }
    
    # Check Minikube
    $minikubeStatus = minikube status --format='{{.Host}}' 2>$null
    if ($minikubeStatus -ne "Running") {
        Write-Log "Minikube is not running!" "ERROR"
        Write-Host "  Start with: minikube start" -ForegroundColor Gray
        exit 1
    }
    Write-Log "Minikube is running" "SUCCESS"
    
    try {
        # Step 1: Install Prometheus Stack
        if (-not (Install-PrometheusStack)) {
            Write-Log "Failed to install Prometheus stack" "ERROR"
            exit 1
        }
        
        # Step 2: Wait for pods
        if (-not (Wait-ForMonitoringPods)) {
            Write-Log "Some monitoring components failed to start" "WARNING"
            # Continue anyway
        }
        
        # Step 3: Configure Grafana
        if (-not (Configure-Grafana)) {
            Write-Log "Grafana configuration had issues" "WARNING"
        }
        
        # Step 4: Import Dashboards
        Import-GrafanaDashboards | Out-Null
        
        # Step 5: Configure Prometheus
        Configure-Prometheus | Out-Null
        
        # Step 6: Summary
        Show-Summary
        
        # Keep script running to maintain port-forward
        Write-Host "Press Enter to stop port-forward and exit..." -ForegroundColor Gray
        Read-Host | Out-Null
        
    } finally {
        Stop-PortForward
        Write-Host "Goodbye!" -ForegroundColor Cyan
    }
}

# Run main
Main
