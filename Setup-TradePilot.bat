@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo === TradePilot full setup ===
echo.

if not exist "frontend\dist\index.html" (
  echo ERROR: frontend\dist is missing. Use the Full Package zip.
  pause
  exit /b 1
)
if not exist "backend\requirements.txt" (
  echo ERROR: backend folder is incomplete.
  pause
  exit /b 1
)

set "PY="
if exist "runtime\python\python.exe" set "PY=%~dp0runtime\python\python.exe"

if not defined PY (
  where py >nul 2>&1 && py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
)
if not defined PY (
  where py >nul 2>&1 && py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)

if not defined PY (
  echo ERROR: No portable runtime\python and no system Python found.
  echo Re-copy the Full Package zip, or install Python 3.11+ from python.org
  pause
  exit /b 1
)

echo Using Python: %PY%

REM If portable runtime exists but packages are missing, install them.
"%PY%" -c "import fastapi,uvicorn,dotenv" >nul 2>&1
if errorlevel 1 (
  echo Installing packages into the portable runtime / environment...
  "%PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  "%PY%" -m pip install -r "backend\requirements.txt"
  if errorlevel 1 goto :fail
) else (
  echo Packages already available.
)

if not exist "backend\.env" (
  if exist "backend\.env.example" copy /Y "backend\.env.example" "backend\.env" >nul
  echo Created backend\.env
  echo.
  echo IMPORTANT: edit backend\.env and set at least:
  echo   DATABASE_URL=... your Supabase pooler URI ...
  echo   EXECUTION_ENABLED=false
  echo Optional: OPENAI_API_KEY
) else (
  echo Keeping existing backend\.env
)

echo.
echo Setup OK.
echo Next:
echo  1. Install/login MetaTrader 5 on this PC
echo  2. Edit backend\.env if Supabase shows unavailable
echo  3. Double-click TradePilot.bat
echo.
pause
exit /b 0

:fail
echo ERROR: package install failed. Check internet access and try again.
pause
exit /b 1
