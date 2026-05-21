#!/bin/bash

echo ""
echo "[INFO] Stopping Cognimend system..."
echo ""

docker-compose down

if [ $? -eq 0 ]; then
    echo ""
    echo "[OK] All services stopped"
    echo ""
else
    echo ""
    echo "[ERROR] Failed to stop services"
    exit 1
fi
