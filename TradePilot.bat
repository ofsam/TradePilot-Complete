@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "frontend\dist\index.html" (
  echo ERROR: frontend\dist missing. Use the Full Package zip.
  pause
  exit /b 1
)

if not exist "runtime\python\python.exe" if not exist "backend\.venv\Scripts\python.exe" (
  echo First run setup...
  call "%~dp0Setup-TradePilot.bat"
)

if not exist "runtime\python\python.exe" if not exist "backend\.venv\Scripts\python.exe" (
  echo Setup incomplete.
  pause
  exit /b 1
)

if not exist "backend\.env" (
  echo WARNING: backend\.env missing. Creating from example.
  copy /Y "backend\.env.example" "backend\.env" >nul
  echo Edit DATABASE_URL in backend\.env then press any key.
  notepad "backend\.env"
  pause
)

echo Starting TradePilot...
echo If the window does not open, wait up to 2 minutes for first startup.
echo Log: runtime\tradepilot-launch.log
echo.

REM Use python.exe so errors are visible if launch fails.
if exist "runtime\python\python.exe" (
  "runtime\python\python.exe" "%~dp0desktop\launch.py"
) else (
  "backend\.venv\Scripts\python.exe" "%~dp0desktop\launch.py"
)

if errorlevel 1 (
  echo.
  echo TradePilot failed to open.
  if exist "runtime\tradepilot-launch.log" type "runtime\tradepilot-launch.log"
  echo.
  echo You can still try: http://127.0.0.1:8000/
  pause
)
exit /b %ERRORLEVEL%
