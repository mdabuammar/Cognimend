#!/bin/bash

echo ""
echo "========================================"
echo "           CLEANUP WARNING"
echo "========================================"
echo ""
echo "This will PERMANENTLY DELETE:"
echo "  ✓ All databases (PostgreSQL)"
echo "  ✓ All vector embeddings (Qdrant)"
echo "  ✓ All cache data (Redis)"
echo "  ✓ All logs and containers"
echo ""
read -p "Are you sure? Type 'yes' to confirm: " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "[INFO] Cleaning up all data..."
    echo ""
    
    docker-compose down -v
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "[OK] All data removed"
        echo ""
        echo "To restart: ./start.sh"
        echo ""
    else
        echo ""
        echo "[ERROR] Cleanup failed"
        exit 1
    fi
else
    echo ""
    echo "[CANCEL] Cleanup cancelled"
    echo ""
fi
