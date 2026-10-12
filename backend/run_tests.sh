#!/usr/bin/env bash
# 在已建好的虚拟环境里运行后端测试。
# 依赖：先执行一次 `uv sync --python 3.11`
set -e
cd "$(dirname "$0")"
exec .venv/Scripts/python.exe -m unittest discover -s tests -v
