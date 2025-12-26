@echo off
title Project Greenlight - Web UI
cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo ============================================================
echo   Project Greenlight - Starting Web UI
echo ============================================================
echo.

REM Check if Python is available
py --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Check if npm dependencies are installed
if not exist "web\node_modules" (
    echo Installing npm dependencies...
    cd web
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install npm dependencies
        pause
        exit /b 1
    )
    cd ..
    echo.
)

echo Starting API server and Next.js frontend...
echo Web UI will open at http://localhost:3000
echo.
echo Press Ctrl+C to stop the server.
echo.

py -m greenlight %*

echo.
echo ============================================================
echo   Server stopped.
echo ============================================================
pause
