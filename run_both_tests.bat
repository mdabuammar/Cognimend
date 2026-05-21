@echo off
REM API Test Suite for Upload and Query Services
REM Test 1: Upload Document (working)
REM Test 2: Query Documents (requires OpenAI API key)

echo ====================================================
echo API Test Results
echo ====================================================
echo.
echo TEST 1: Upload a Document
echo ====================================================
echo Command: curl -X POST http://localhost:8001/upload -F "file=@sample.txt" -F "title=Company Policy"
echo.
curl -X POST http://localhost:8001/upload -F "file=@sample.txt" -F "title=Company Policy"
echo.
echo.
echo ====================================================
echo TEST 2: Query Documents
echo ====================================================
echo Command: curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d "{\"question\": \"What is the leave policy?\"}"
echo.
echo NOTE: Query service requires OpenAI API key configured in backend/.env
echo If you see a connection error, the query service may not be running or needs the API key setup.
echo.
curl -X POST http://localhost:8002/query -H "Content-Type: application/json" -d "{\"question\": \"What is the leave policy?\"}"
echo.
echo.
echo ====================================================
echo Test Summary
echo ====================================================
echo Upload Service (8001): Should see JSON response with document_id
echo Query Service (8002): Requires OpenAI API key in backend/.env
echo ====================================================
