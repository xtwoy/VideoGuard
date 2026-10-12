@echo off
REM 在已建好的虚拟环境里运行后端测试。
REM 依赖：先执行一次 `uv sync --python 3.11`
cd /d "%~dp0"
.venv\Scripts\python.exe -m unittest discover -s tests -v
