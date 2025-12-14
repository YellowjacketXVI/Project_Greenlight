@echo off
title Project Greenlight - Web UI
cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo ============================================================
echo   Project Greenlight - Starting Web UI
echo ============================================================
echo.
echo Starting API server and Next.js frontend...
echo Web UI will open at http://localhost:3000
echo.

py -m greenlight %*

