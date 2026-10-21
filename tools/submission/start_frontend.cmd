@echo off
setlocal
cd /d "%~dp0frontend"
if not exist ".next\BUILD_ID" (
    echo Install and build the frontend first: npm ci, then npm run build
    pause
    exit /b 1
)
call npm.cmd run start -- --hostname 127.0.0.1 --port 3000
pause
