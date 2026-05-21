#!/bin/bash

# ============================================================================
# Cognimend RAG System - Stress Test Suite
# ============================================================================
# This script orchestrates comprehensive stress testing for the RAG system
# using both K6 and Locust for different types of load patterns.
#
# Usage:
#   ./stress-test.sh [command] [options]
#
# Commands:
#   smoke       - Quick smoke test (1 min, low load)
#   load        - Standard load test (5 min, moderate load)
#   stress      - Stress test (10 min, high load)
#   spike       - Spike test (sudden traffic bursts)
#   soak        - Endurance test (1 hour, sustained load)
#   breakpoint  - Find system limits (increasing load until failure)
#   report      - Generate HTML report from results
#
# Options:
#   --target URL    - Base URL (default: http://localhost:8000)
#   --k6            - Use K6 only
#   --locust        - Use Locust only
#   --vus N         - Number of virtual users (default varies by test)
#   --duration D    - Test duration (e.g., 5m, 1h)
#   --output DIR    - Output directory for results
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
TARGET_URL="${TARGET_URL:-http://localhost:8000}"
OUTPUT_DIR="${OUTPUT_DIR:-./results}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="${OUTPUT_DIR}/${TIMESTAMP}"
K6_SCRIPT="./comprehensive-test.js"
LOCUST_FILE="./locustfile.py"

# Test profiles
declare -A SMOKE_PROFILE=( ["vus"]=1 ["duration"]="1m" ["rps"]=5 )
declare -A LOAD_PROFILE=( ["vus"]=50 ["duration"]="5m" ["rps"]=100 )
declare -A STRESS_PROFILE=( ["vus"]=200 ["duration"]="10m" ["rps"]=500 )
declare -A SPIKE_PROFILE=( ["vus"]=500 ["duration"]="5m" ["rps"]=1000 )
declare -A SOAK_PROFILE=( ["vus"]=100 ["duration"]="1h" ["rps"]=200 )

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Cognimend RAG System - Stress Test Suite             ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    local missing=()
    
    if ! command -v k6 &> /dev/null; then
        missing+=("k6")
    fi
    
    if ! command -v locust &> /dev/null; then
        missing+=("locust")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing+=("jq")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_warning "Missing dependencies: ${missing[*]}"
        log_info "Install with:"
        for dep in "${missing[@]}"; do
            case $dep in
                k6)
                    echo "  - K6: https://k6.io/docs/getting-started/installation/"
                    ;;
                locust)
                    echo "  - Locust: pip install locust"
                    ;;
                jq)
                    echo "  - jq: apt-get install jq / brew install jq"
                    ;;
            esac
        done
        return 1
    fi
    
    log_success "All dependencies available"
    return 0
}

setup_results_dir() {
    mkdir -p "$RESULTS_DIR"
    log_info "Results will be saved to: $RESULTS_DIR"
}

check_target_health() {
    log_info "Checking target health: $TARGET_URL"
    
    local endpoints=("upload" "query" "telemetry" "drift-detector" "controller" "evaluation")
    local all_healthy=true
    
    for endpoint in "${endpoints[@]}"; do
        local port
        case $endpoint in
            upload) port=8001 ;;
            query) port=8002 ;;
            telemetry) port=8003 ;;
            drift-detector) port=8004 ;;
            controller) port=8005 ;;
            evaluation) port=8006 ;;
        esac
        
        local health_url="http://localhost:${port}/health"
        local status=$(curl -s -o /dev/null -w "%{http_code}" "$health_url" 2>/dev/null || echo "000")
        
        if [ "$status" = "200" ]; then
            echo -e "  ${GREEN}✓${NC} $endpoint (port $port)"
        else
            echo -e "  ${RED}✗${NC} $endpoint (port $port) - HTTP $status"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = false ]; then
        log_warning "Some services are not healthy. Tests may fail."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_success "All services healthy"
    fi
}

# ============================================================================
# K6 Test Functions
# ============================================================================

run_k6_test() {
    local test_type=$1
    local vus=$2
    local duration=$3
    
    log_info "Running K6 $test_type test: $vus VUs for $duration"
    
    local output_file="$RESULTS_DIR/k6_${test_type}_${TIMESTAMP}.json"
    local html_report="$RESULTS_DIR/k6_${test_type}_${TIMESTAMP}.html"
    
    k6 run \
        --vus "$vus" \
        --duration "$duration" \
        --out json="$output_file" \
        --env BASE_URL="$TARGET_URL" \
        --env TEST_TYPE="$test_type" \
        --summary-trend-stats="avg,min,med,max,p(90),p(95),p(99)" \
        "$K6_SCRIPT" 2>&1 | tee "$RESULTS_DIR/k6_${test_type}_output.log"
    
    log_success "K6 test completed. Results: $output_file"
}

run_k6_breakpoint() {
    log_info "Running K6 breakpoint test (finding system limits)..."
    
    local output_file="$RESULTS_DIR/k6_breakpoint_${TIMESTAMP}.json"
    
    k6 run \
        --vus 1 \
        --stage "30s:10" \
        --stage "1m:50" \
        --stage "1m:100" \
        --stage "1m:200" \
        --stage "1m:300" \
        --stage "1m:500" \
        --stage "30s:0" \
        --out json="$output_file" \
        --env BASE_URL="$TARGET_URL" \
        --env TEST_TYPE="breakpoint" \
        "$K6_SCRIPT" 2>&1 | tee "$RESULTS_DIR/k6_breakpoint_output.log"
    
    log_success "Breakpoint test completed"
}

run_k6_spike() {
    log_info "Running K6 spike test..."
    
    local output_file="$RESULTS_DIR/k6_spike_${TIMESTAMP}.json"
    
    k6 run \
        --vus 1 \
        --stage "10s:10" \
        --stage "1s:500" \
        --stage "30s:500" \
        --stage "1s:10" \
        --stage "30s:10" \
        --stage "1s:500" \
        --stage "30s:500" \
        --stage "10s:0" \
        --out json="$output_file" \
        --env BASE_URL="$TARGET_URL" \
        --env TEST_TYPE="spike" \
        "$K6_SCRIPT" 2>&1 | tee "$RESULTS_DIR/k6_spike_output.log"
    
    log_success "Spike test completed"
}

# ============================================================================
# Locust Test Functions
# ============================================================================

run_locust_test() {
    local test_type=$1
    local users=$2
    local duration=$3
    local spawn_rate=${4:-10}
    
    log_info "Running Locust $test_type test: $users users for $duration"
    
    local output_file="$RESULTS_DIR/locust_${test_type}_${TIMESTAMP}"
    
    # Convert duration to seconds
    local duration_seconds
    if [[ $duration == *m ]]; then
        duration_seconds=$((${duration%m} * 60))
    elif [[ $duration == *h ]]; then
        duration_seconds=$((${duration%h} * 3600))
    else
        duration_seconds=${duration%s}
    fi
    
    locust \
        -f "$LOCUST_FILE" \
        --headless \
        -u "$users" \
        -r "$spawn_rate" \
        -t "${duration_seconds}s" \
        --host "$TARGET_URL" \
        --csv="$output_file" \
        --html="$output_file.html" \
        2>&1 | tee "$RESULTS_DIR/locust_${test_type}_output.log"
    
    log_success "Locust test completed. Results: ${output_file}.html"
}

run_locust_distributed() {
    local users=$1
    local duration=$2
    local workers=${3:-4}
    
    log_info "Running distributed Locust test with $workers workers"
    
    # Start master
    locust \
        -f "$LOCUST_FILE" \
        --master \
        --expect-workers="$workers" \
        --headless \
        -u "$users" \
        -r 50 \
        -t "$duration" \
        --host "$TARGET_URL" \
        --csv="$RESULTS_DIR/locust_distributed_${TIMESTAMP}" \
        --html="$RESULTS_DIR/locust_distributed_${TIMESTAMP}.html" &
    
    local master_pid=$!
    
    # Start workers
    for i in $(seq 1 "$workers"); do
        locust \
            -f "$LOCUST_FILE" \
            --worker \
            --master-host=127.0.0.1 &
    done
    
    wait $master_pid
    
    log_success "Distributed test completed"
}

# ============================================================================
# Report Generation
# ============================================================================

generate_report() {
    log_info "Generating combined test report..."
    
    local report_file="$RESULTS_DIR/combined_report.html"
    
    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognimend - Stress Test Report</title>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #d97706;
            --error: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--primary), #1e40af);
            color: white;
            border-radius: 1rem;
        }
        .header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.9; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .card {
            background: var(--card);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .card h3 {
            color: var(--primary);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e2e8f0;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #f1f5f9;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #64748b; }
        .metric-value { font-weight: 600; }
        .status-pass { color: var(--success); }
        .status-warn { color: var(--warning); }
        .status-fail { color: var(--error); }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        th { background: #f8fafc; font-weight: 600; }
        tr:hover { background: #f8fafc; }
        .footer {
            text-align: center;
            padding: 2rem;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Cognimend Stress Test Report</h1>
            <p>Generated: TIMESTAMP_PLACEHOLDER</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>📊 Test Summary</h3>
                <div class="metric">
                    <span class="metric-label">Total Tests Run</span>
                    <span class="metric-value">TESTS_COUNT</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Duration</span>
                    <span class="metric-value">TOTAL_DURATION</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Max VUs</span>
                    <span class="metric-value">MAX_VUS</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Requests</span>
                    <span class="metric-value">TOTAL_REQUESTS</span>
                </div>
            </div>
            
            <div class="card">
                <h3>⚡ Performance Metrics</h3>
                <div class="metric">
                    <span class="metric-label">Avg Response Time</span>
                    <span class="metric-value">AVG_RESPONSE_TIME</span>
                </div>
                <div class="metric">
                    <span class="metric-label">P95 Response Time</span>
                    <span class="metric-value">P95_RESPONSE_TIME</span>
                </div>
                <div class="metric">
                    <span class="metric-label">P99 Response Time</span>
                    <span class="metric-value">P99_RESPONSE_TIME</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Max Throughput</span>
                    <span class="metric-value">MAX_THROUGHPUT</span>
                </div>
            </div>
            
            <div class="card">
                <h3>✅ Reliability</h3>
                <div class="metric">
                    <span class="metric-label">Success Rate</span>
                    <span class="metric-value status-pass">SUCCESS_RATE</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Error Rate</span>
                    <span class="metric-value">ERROR_RATE</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Timeout Rate</span>
                    <span class="metric-value">TIMEOUT_RATE</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Checks Passed</span>
                    <span class="metric-value status-pass">CHECKS_PASSED</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>📈 Test Results by Endpoint</h3>
            <table>
                <thead>
                    <tr>
                        <th>Endpoint</th>
                        <th>Requests</th>
                        <th>Avg (ms)</th>
                        <th>P95 (ms)</th>
                        <th>Error %</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ENDPOINT_ROWS
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Cognimend RAG System - Stress Test Suite v1.0</p>
            <p>Results Directory: RESULTS_DIR_PLACEHOLDER</p>
        </div>
    </div>
</body>
</html>
EOF

    # Replace placeholders with actual data
    sed -i "s/TIMESTAMP_PLACEHOLDER/$(date '+%Y-%m-%d %H:%M:%S')/g" "$report_file"
    sed -i "s|RESULTS_DIR_PLACEHOLDER|$RESULTS_DIR|g" "$report_file"
    
    log_success "Report generated: $report_file"
}

# ============================================================================
# Main Commands
# ============================================================================

run_smoke_test() {
    log_info "Starting smoke test..."
    check_target_health
    run_k6_test "smoke" "${SMOKE_PROFILE[vus]}" "${SMOKE_PROFILE[duration]}"
    run_locust_test "smoke" "${SMOKE_PROFILE[vus]}" "${SMOKE_PROFILE[duration]}" 1
}

run_load_test() {
    log_info "Starting load test..."
    check_target_health
    run_k6_test "load" "${LOAD_PROFILE[vus]}" "${LOAD_PROFILE[duration]}"
    run_locust_test "load" "${LOAD_PROFILE[vus]}" "${LOAD_PROFILE[duration]}" 10
}

run_stress_test() {
    log_info "Starting stress test..."
    check_target_health
    run_k6_test "stress" "${STRESS_PROFILE[vus]}" "${STRESS_PROFILE[duration]}"
    run_locust_test "stress" "${STRESS_PROFILE[vus]}" "${STRESS_PROFILE[duration]}" 20
}

run_spike_test() {
    log_info "Starting spike test..."
    check_target_health
    run_k6_spike
}

run_soak_test() {
    log_info "Starting soak test (this will take ~1 hour)..."
    check_target_health
    run_k6_test "soak" "${SOAK_PROFILE[vus]}" "${SOAK_PROFILE[duration]}"
}

run_breakpoint_test() {
    log_info "Starting breakpoint test (finding system limits)..."
    check_target_health
    run_k6_breakpoint
}

run_all_tests() {
    log_info "Running complete test suite..."
    check_target_health
    
    run_smoke_test
    sleep 30
    
    run_load_test
    sleep 60
    
    run_stress_test
    sleep 60
    
    run_spike_test
    sleep 30
    
    generate_report
    
    log_success "All tests completed!"
}

# ============================================================================
# CLI
# ============================================================================

show_help() {
    cat << EOF
Cognimend RAG System - Stress Test Suite

Usage: $0 [command] [options]

Commands:
  smoke       Run quick smoke test (1 min, low load)
  load        Run standard load test (5 min, moderate load)
  stress      Run stress test (10 min, high load)
  spike       Run spike test (sudden traffic bursts)
  soak        Run endurance test (1 hour, sustained load)
  breakpoint  Find system limits (increasing load until failure)
  all         Run complete test suite
  report      Generate HTML report from results

Options:
  --target URL    Base URL (default: $TARGET_URL)
  --output DIR    Output directory (default: $OUTPUT_DIR)
  --vus N         Override virtual users count
  --duration D    Override test duration
  --help          Show this help

Examples:
  $0 smoke                      # Quick smoke test
  $0 load --target http://api.example.com
  $0 stress --vus 500 --duration 15m
  $0 all                        # Run complete suite

Environment Variables:
  TARGET_URL    Base URL for tests
  OUTPUT_DIR    Directory for results

EOF
}

# Parse arguments
COMMAND=""
CUSTOM_VUS=""
CUSTOM_DURATION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        smoke|load|stress|spike|soak|breakpoint|all|report)
            COMMAND=$1
            shift
            ;;
        --target)
            TARGET_URL=$2
            shift 2
            ;;
        --output)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --vus)
            CUSTOM_VUS=$2
            shift 2
            ;;
        --duration)
            CUSTOM_DURATION=$2
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_banner
    
    if [ -z "$COMMAND" ]; then
        show_help
        exit 1
    fi
    
    # Check dependencies for non-report commands
    if [ "$COMMAND" != "report" ]; then
        check_dependencies || exit 1
    fi
    
    setup_results_dir
    
    case $COMMAND in
        smoke)
            run_smoke_test
            ;;
        load)
            run_load_test
            ;;
        stress)
            run_stress_test
            ;;
        spike)
            run_spike_test
            ;;
        soak)
            run_soak_test
            ;;
        breakpoint)
            run_breakpoint_test
            ;;
        all)
            run_all_tests
            ;;
        report)
            generate_report
            ;;
    esac
    
    echo ""
    log_success "Test execution complete!"
    log_info "Results saved to: $RESULTS_DIR"
}

main
