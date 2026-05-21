Write-Host "🚀 DriftGuard: MAX CONFIDENCE MODE (90%+)" -ForegroundColor Green

cd backend

# 1. Restart with new config
docker-compose restart upload-service query-service

# 2. Rechunk ALL documents
Write-Host "🔄 Rechunking all PDFs..." -ForegroundColor Yellow
curl -X POST "http://localhost:8001/rechunk-all"

# 3. Test confidence
Write-Host "`n🧪 Testing confidence..." -ForegroundColor Cyan
curl -X POST "http://localhost:8002/query" -H "Content-Type: application/json" -d "{\"question\":\"What is the main objective of the proposed lightweight deep learning framework?\"}" | ConvertFrom-Json

Write-Host "`n🎉 MAX CONFIDENCE ACTIVE! Test at http://localhost:3000`nExpected: 90%+ confidence" -ForegroundColor Green
