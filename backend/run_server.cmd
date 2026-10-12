@echo off
REM 启动本地后端（127.0.0.1:8000）。需已执行 uv sync 并配置好 .env。
REM 前置条件：ffprobe 必须在 PATH，否则真实上传会以 422 失败。
cd /d "%~dp0"
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
