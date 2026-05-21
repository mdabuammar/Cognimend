@echo off
REM ============================================================
REM DriftGuard Backup Script for Windows
REM ============================================================

setlocal enabledelayedexpansion

REM Set default values
set BACKUP_TYPE=all
set CLEANUP=false
set BACKUP_DIR=.\backups

REM Parse arguments
:parse_args
if "%~1"=="" goto run_backup
if /i "%~1"=="--type" (
    set BACKUP_TYPE=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--cleanup" (
    set CLEANUP=true
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    goto show_help
)
shift
goto parse_args

:show_help
echo.
echo DriftGuard Backup Script
echo.
echo Usage: backup.bat [options]
echo.
echo Options:
echo   --type TYPE    Backup type: all, postgres, qdrant, redis (default: all)
echo   --cleanup      Clean up old backups after backup
echo   --help         Show this help message
echo.
echo Environment Variables:
echo   POSTGRES_HOST     PostgreSQL host (default: localhost)
echo   POSTGRES_PORT     PostgreSQL port (default: 5432)
echo   POSTGRES_DB       Database name (default: cognimend)
echo   POSTGRES_USER     Database user (default: postgres)
echo   POSTGRES_PASSWORD Database password
echo   QDRANT_HOST       Qdrant host (default: localhost)
echo   QDRANT_PORT       Qdrant port (default: 6333)
echo   REDIS_HOST        Redis host (default: localhost)
echo   REDIS_PORT        Redis port (default: 6379)
echo.
exit /b 0

:run_backup
echo.
echo ============================================================
echo DriftGuard Backup - %date% %time%
echo ============================================================
echo Backup Type: %BACKUP_TYPE%
echo Backup Dir:  %BACKUP_DIR%
echo Cleanup:     %CLEANUP%
echo ============================================================
echo.

REM Create backup directory if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Change to backend directory
cd /d "%~dp0.."

REM Run Python backup script
if "%CLEANUP%"=="true" (
    python scripts\backup.py --type %BACKUP_TYPE% --cleanup --backup-dir "%BACKUP_DIR%"
) else (
    python scripts\backup.py --type %BACKUP_TYPE% --backup-dir "%BACKUP_DIR%"
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo BACKUP FAILED with exit code %ERRORLEVEL%
    echo ============================================================
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo BACKUP COMPLETED SUCCESSFULLY
echo ============================================================
echo.

endlocal
