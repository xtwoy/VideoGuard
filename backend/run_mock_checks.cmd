@echo off
setlocal
cd /d "%~dp0"
set "VG_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "VG_PYTHON=.venv\Scripts\python.exe"
%VG_PYTHON% -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
%VG_PYTHON% -m fixtures.validate
if errorlevel 1 exit /b 1
%VG_PYTHON% -m fixtures.generate --check
if errorlevel 1 exit /b 1
%VG_PYTHON% -m fixtures.truth_table
if errorlevel 1 exit /b 1
%VG_PYTHON% -m fixtures.compare_pead --check
if errorlevel 1 exit /b 1
echo Mock validation passed. Reports are in backend\reports.
