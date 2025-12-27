@echo off
echo ============================================================
echo   Project Greenlight - Starting UI
echo ============================================================
echo.

:: Kill any existing processes on ports 3000 and 8000
echo Clearing ports 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
echo Ports cleared.
echo.

:: Start the UI
echo Starting Greenlight UI...
echo   API Server: http://localhost:8000
echo   Frontend:   http://localhost:3000
echo.
py -m greenlight

