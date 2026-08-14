@echo off
title Jarvis Assistant Launcher
cd /d "%~dp0"
set PYTHONPATH=%~dp0backend;%~dp0
"%~dp0.venv\Scripts\python.exe" "%~dp0run_jarvis.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Jarvis encountered an issue. See launcher.log for details.
    pause
)
