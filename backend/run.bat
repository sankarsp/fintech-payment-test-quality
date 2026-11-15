@echo off
REM Start the API on port 8800 (override: set PORT=9000 before running)
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8800
python -m uvicorn app.main:app --reload --port %PORT%
