@echo off
cd /d D:\Project
echo Testing Upload Service...
echo.
echo TEST 1: Upload Document
echo ========================
curl -X POST http://localhost:8001/upload -F "file=@sample.txt" -F "title=Company Policy"
echo.
echo.
echo TEST 2: Query Service
echo ========================
curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d "{\"question\": \"What is the leave policy?\"}"
