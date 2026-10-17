@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing virtualenv Python at .venv\Scripts\python.exe
  exit /b 1
)

if /I "%~1"=="--apply" (
  .venv\Scripts\python.exe fix_linz_qualifying_surface.py --apply
) else (
  .venv\Scripts\python.exe fix_linz_qualifying_surface.py
)

endlocal
