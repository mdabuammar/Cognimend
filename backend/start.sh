#!/bin/bash

echo ""
echo "========================================"
echo "   Cognimend Autonomous RAG System"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "[ERROR] .env file not found!"
    echo ""
    echo "Please create a .env file with your OPENAI_API_KEY"
    echo "Example:"
    echo "  OPENAI_API_KEY=<redacted-api-key>your-key-here"
    echo "  POSTGRES_DB=cognimend"
    echo "  POSTGRES_USER=postgres"
    echo "  POSTGRES_PASSWORD=password123"
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running!"
    echo ""
    echo "Please start Docker Desktop or Docker daemon"
    echo ""
    exit 1
fi

echo "[INFO] Building Docker images..."
echo ""
docker-compose build

if [ $? -ne 0 ]; then
    echo "[ERROR] Docker build failed!"
    exit 1
fi

echo ""
echo "[INFO] Starting all services..."
echo ""
docker-compose up -d

if [ $? -ne 0 ]; then
    echo "[ERROR] Docker compose failed!"
    exit 1
fi

echo ""
echo "[INFO] Waiting for services to be healthy..."
sleep 15

echo ""
echo "========================================"
echo "         HEALTH CHECK REPORT"
echo "========================================"
echo ""

services=(
    "Upload:8001"
    "Query:8002"
    "Telemetry:8003"
    "Drift Detector:8004"
    "Controller:8005"
    "Evaluation:8006"
)

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "[OK]   $name (port $port)"
    else
        echo "[FAIL] $name (port $port)"
    fi
done

echo ""
echo "========================================"
echo "          SYSTEM IS RUNNING!"
echo "========================================"
echo ""
echo "Access services at:"
echo "  Upload:        http://localhost:8001"
echo "  Query:         http://localhost:8002"
echo "  Telemetry:     http://localhost:8003"
echo "  Dashboard:     http://localhost:8003/dashboard/stats"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
echo "Stop system:"
echo "  docker-compose down"
echo ""
