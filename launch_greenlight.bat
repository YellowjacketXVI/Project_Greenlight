@echo off
title Project Greenlight
cd /d "%~dp0"
set PYTHONPATH=%~dp0
py greenlight/__main__.py %*
pause

