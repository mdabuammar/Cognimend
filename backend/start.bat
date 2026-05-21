@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo    Cognimend Autonomous RAG System
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo.
    echo Please create a .env file with your OPENAI_API_KEY
    echo Example:
    echo   OPENAI_API_KEY=<redacted-api-key>your-key-here
    echo   POSTGRES_DB=cognimend
    echo   POSTGRES_USER=postgres
    echo   POSTGRES_PASSWORD=password123
    echo.
    pause
    exit /b 1
)

REM Check if Docker is running
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH!
    echo.
    echo Please install Docker Desktop from https://www.docker.com
    echo.
    pause
    exit /b 1
)

echo [INFO] Building Docker images...
echo.
docker-compose build

if errorlevel 1 (
    echo [ERROR] Docker build failed!
    pause
    exit /b 1
)

echo.
echo [INFO] Starting all services...
echo.
docker-compose up -d

if errorlevel 1 (
    echo [ERROR] Docker compose failed!
    pause
    exit /b 1
)

echo.
echo [INFO] Waiting for services to be healthy...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo        HEALTH CHECK REPORT
echo ========================================
echo.

setlocal enabledelayedexpansion
set "services=Upload:8001,Query:8002,Telemetry:8003,Drift Detector:8004,Controller:8005,Evaluation:8006"

for %%S in (%services%) do (
    for /f "tokens=1,2 delims=:" %%A in ("%%S") do (
        for /f "tokens=*" %%U in ('curl -s http://localhost:%%B/health 2^>nul ^| find "healthy"') do (
            if "%%U"=="" (
                echo [FAIL] %%A ^(port %%B^)
            ) else (
                echo [OK]   %%A ^(port %%B^)
            )
        )
    )
)

echo.
echo ========================================
echo          SYSTEM IS RUNNING!
echo ========================================
echo.
echo Access services at:
echo   Upload:        http://localhost:8001
echo   Query:         http://localhost:8002
echo   Telemetry:     http://localhost:8003
echo   Dashboard:     http://localhost:8003/dashboard/stats
echo.
echo View logs:
echo   docker-compose logs -f
echo.
echo Stop system:
echo   docker-compose down
echo.
pause
