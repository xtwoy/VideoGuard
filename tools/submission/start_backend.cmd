@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo Install backend dependencies first: uv sync --locked --python 3.11
    pause
    exit /b 1
)
if not exist ".env" (
    echo Copy backend\.env.example to backend\.env and configure the services first.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
