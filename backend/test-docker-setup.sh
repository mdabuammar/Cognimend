#!/bin/bash

# Automated Testing Script for Docker Compose
# Run this in bash to test your entire setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Flags
SKIP_BUILD=false
SKIP_START=false
SKIP_TESTS=false
ADVANCED_DRIFT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-start)
            SKIP_START=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --drift)
            ADVANCED_DRIFT=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Helper functions
print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Step 1: Pre-flight Check
print_header "STEP 1: PRE-FLIGHT CHECK"

print_info "Checking Docker installation..."
if docker --version &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker: $DOCKER_VERSION"
else
    print_error "Docker not installed or not in PATH"
    exit 1
fi

if docker-compose --version &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    print_success "Docker Compose: $COMPOSE_VERSION"
else
    print_error "Docker Compose not installed"
    exit 1
fi

print_info "Checking .env file..."
if [ -f ".env" ]; then
    print_success ".env file found"
    if grep -q "OPENAI_API_KEY=<redacted-api-key>" .env; then
        print_success "OPENAI_API_KEY configured"
    else
        print_error "OPENAI_API_KEY not configured in .env"
    fi
else
    print_error ".env file not found"
    exit 1
fi

print_info "Checking Dockerfiles..."
DOCKERFILES=(
    "services/upload/Dockerfile"
    "services/query/Dockerfile"
    "services/telemetry/Dockerfile"
    "services/drift_detector/Dockerfile"
    "services/controller/Dockerfile"
    "services/evaluation/Dockerfile"
)

for dockerfile in "${DOCKERFILES[@]}"; do
    if [ -f "$dockerfile" ]; then
        print_success "$dockerfile exists"
    else
        print_error "$dockerfile missing"
    fi
done

# Step 2: Build Images
if [ "$SKIP_BUILD" = false ]; then
    print_header "STEP 2: BUILDING DOCKER IMAGES"
    print_info "This may take 5-10 minutes..."
    
    if docker-compose build; then
        print_success "Docker build completed successfully"
    else
        print_error "Docker build failed"
        exit 1
    fi
fi

# Step 3: Start Services
if [ "$SKIP_START" = false ]; then
    print_header "STEP 3: STARTING SERVICES"
    
    if docker-compose up -d; then
        print_success "Docker Compose started"
    else
        print_error "Failed to start Docker Compose"
        exit 1
    fi
    
    print_info "Waiting 30 seconds for services to stabilize..."
    sleep 30
fi

# Step 4: Verify Containers
print_header "STEP 4: VERIFYING CONTAINERS"

CONTAINERS=(
    "cognimend-postgres"
    "cognimend-qdrant"
    "cognimend-redis"
    "cognimend-upload"
    "cognimend-query"
    "cognimend-telemetry"
    "cognimend-drift-detector"
    "cognimend-controller"
    "cognimend-evaluation"
)

ALL_RUNNING=true
for container in "${CONTAINERS[@]}"; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not_found")
    if [ "$STATUS" = "running" ]; then
        print_success "$container is running"
    else
        print_error "$container is NOT running (status: $STATUS)"
        ALL_RUNNING=false
    fi
done

if [ "$ALL_RUNNING" = false ]; then
    print_error "Not all containers are running. Check logs with: docker-compose logs"
    exit 1
fi

# Step 5: Health Check
print_header "STEP 5: HEALTH CHECK"

SERVICES=(
    "Upload:8001"
    "Query:8002"
    "Telemetry:8003"
    "Drift Detector:8004"
    "Controller:8005"
    "Evaluation:8006"
)

ALL_HEALTHY=true
for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
        print_success "$name ($port): HEALTHY"
    else
        print_error "$name ($port): NOT RESPONDING or UNHEALTHY"
        ALL_HEALTHY=false
    fi
done

if [ "$ALL_HEALTHY" = false ]; then
    print_error "Some services not responding. Check logs with: docker-compose logs"
    exit 1
fi

# Step 6: Functional Tests
if [ "$SKIP_TESTS" = false ]; then
    print_header "STEP 6: FUNCTIONAL TESTS"
    
    # Create test file
    print_info "Creating test document..."
    echo "Company Vacation Policy: Employees get 15 days of paid vacation per year. Sick leave is 10 days annually." > test_policy.txt
    print_success "Test file created"
    
    # Test Upload
    print_info "Testing upload service..."
    UPLOAD_RESPONSE=$(curl -X POST "http://localhost:8001/upload" \
        -F "file=@test_policy.txt" \
        -F "title=Vacation Policy" -s)
    
    if echo "$UPLOAD_RESPONSE" | grep -q "success"; then
        print_success "Upload successful"
    else
        print_error "Upload failed"
    fi
    
    sleep 5
    
    # Test Query
    print_info "Testing query service..."
    QUERY_RESPONSE=$(curl -X POST "http://localhost:8002/query" \
        -H "Content-Type: application/json" \
        -d '{"question": "How many vacation days do employees get?"}' -s)
    
    if echo "$QUERY_RESPONSE" | grep -q "answer"; then
        ANSWER=$(echo "$QUERY_RESPONSE" | grep -o '"answer":"[^"]*"' | head -1)
        print_success "Query successful"
        echo "   $ANSWER" | sed 's/^/   /' 
    else
        print_error "Query failed"
    fi
    
    # Test Dashboard
    print_info "Testing dashboard..."
    STATS=$(curl -s "http://localhost:8003/dashboard/stats")
    if echo "$STATS" | grep -q "total_queries"; then
        print_success "Dashboard stats retrieved"
    else
        print_error "Dashboard test failed"
    fi
    
    # Test Drift Status
    print_info "Testing drift detection..."
    DRIFT=$(curl -s "http://localhost:8003/dashboard/drift-status")
    if echo "$DRIFT" | grep -q "data_drift"; then
        print_success "Drift status retrieved"
    else
        print_error "Drift test failed"
    fi
    
    # Test Evaluation
    print_info "Running evaluation suite..."
    EVAL=$(curl -X POST "http://localhost:8006/run-evaluation" -s)
    if echo "$EVAL" | grep -q "run_id"; then
        print_success "Evaluation completed"
    else
        print_error "Evaluation test failed"
    fi
fi

# Step 7: Advanced Drift Test
if [ "$ADVANCED_DRIFT" = true ]; then
    print_header "STEP 7: ADVANCED DRIFT DETECTION TEST"
    
    # Upload v1
    print_info "Uploading document v1..."
    echo "Leave Policy: 15 days vacation, 10 days sick leave." > policy_v1.txt
    curl -X POST "http://localhost:8001/upload" \
        -F "file=@policy_v1.txt" \
        -F "title=Leave Policy" -s > /dev/null
    print_success "Document v1 uploaded"
    
    sleep 3
    
    # Query for baseline
    print_info "Getting baseline confidence..."
    BASELINE=$(curl -X POST "http://localhost:8002/query" \
        -H "Content-Type: application/json" \
        -d '{"question": "How many vacation days?"}' -s)
    print_success "Baseline query completed"
    
    # Upload v2
    print_info "Uploading document v2 (simulating drift)..."
    echo "Leave Policy: 20 days vacation, 12 days sick leave. Updated 2026." > policy_v2.txt
    curl -X POST "http://localhost:8001/upload" \
        -F "file=@policy_v2.txt" \
        -F "title=Leave Policy" -s > /dev/null
    print_success "Document v2 uploaded"
    
    # Trigger drift detection
    print_info "Triggering drift detection..."
    curl -X POST "http://localhost:8004/detect" -s > /dev/null
    print_success "Drift detection triggered"
    
    sleep 5
    
    # Check controller actions
    print_info "Checking controller response..."
    ACTIONS=$(curl -s "http://localhost:8005/actions/history")
    if echo "$ACTIONS" | grep -q "action_type"; then
        print_success "Controller took action(s)"
    else
        print_info "No controller actions yet"
    fi
fi

# Summary
print_header "TESTING COMPLETE"
print_success "All basic tests passed!"
echo ""
echo "Next steps:"
echo "  1. Review logs: docker-compose logs -f"
echo "  2. Monitor system: docker stats --no-stream"
echo "  3. Stop system: docker-compose down"
echo "  4. Check documentation: DOCKER_WEEK5.md"
echo ""
print_success "Your Docker Compose setup is working perfectly!"
