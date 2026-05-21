@echo off
REM ============================================================
REM DriftGuard Restore Script for Windows
REM ============================================================

setlocal enabledelayedexpansion

REM Set default values
set RESTORE_TYPE=
set BACKUP_FILE=
set LIST_ONLY=false
set FORCE=false
set BACKUP_DIR=.\backups

REM Parse arguments
:parse_args
if "%~1"=="" goto check_args
if /i "%~1"=="--type" (
    set RESTORE_TYPE=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--file" (
    set BACKUP_FILE=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--list" (
    set LIST_ONLY=true
    shift
    goto parse_args
)
if /i "%~1"=="--force" (
    set FORCE=true
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
echo DriftGuard Restore Script
echo.
echo Usage: restore.bat --type TYPE [options]
echo.
echo Required:
echo   --type TYPE    Restore type: postgres, qdrant, redis
echo.
echo Options:
echo   --file FILE    Specific backup file to restore (uses latest if not specified)
echo   --list         List available backups
echo   --force        Skip confirmation prompt
echo   --help         Show this help message
echo.
exit /b 0

:check_args
if "%RESTORE_TYPE%"=="" (
    echo ERROR: --type is required
    echo Use --help for usage information
    exit /b 1
)

:run_restore
echo.
echo ============================================================
echo DriftGuard Restore - %date% %time%
echo ============================================================
echo Restore Type: %RESTORE_TYPE%
echo Backup Dir:   %BACKUP_DIR%
echo ============================================================
echo.

REM Change to backend directory
cd /d "%~dp0.."

REM Build command
set CMD=python scripts\restore.py --type %RESTORE_TYPE% --backup-dir "%BACKUP_DIR%"

if "%LIST_ONLY%"=="true" (
    set CMD=%CMD% --list
)
if not "%BACKUP_FILE%"=="" (
    set CMD=%CMD% --file "%BACKUP_FILE%"
)
if "%FORCE%"=="true" (
    set CMD=%CMD% --force
)

REM Run Python restore script
%CMD%

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo RESTORE FAILED with exit code %ERRORLEVEL%
    echo ============================================================
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo RESTORE COMPLETED
echo ============================================================
echo.

endlocal
