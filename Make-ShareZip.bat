@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "frontend\dist\index.html" (
  echo ERROR: frontend\dist\index.html missing. Cannot build a runnable share zip.
  pause
  exit /b 1
)
if not exist "backend\_recover\pyc_backup" (
  echo ERROR: backend\_recover\pyc_backup missing. Strategy routes need it.
  pause
  exit /b 1
)

set "STAGING=%TEMP%\TradePilot-Share-%RANDOM%"
set "OUTDIR=%~dp0share"
set "ZIP=%OUTDIR%\TradePilot-Portable.zip"

echo Staging share package...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%" || exit /b 1
mkdir "%OUTDIR%" 2>nul

robocopy "%~dp0backend\app" "%STAGING%\backend\app" /E /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0backend\_recover\pyc_backup" "%STAGING%\backend\_recover\pyc_backup" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0frontend\dist" "%STAGING%\frontend\dist" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0desktop" "%STAGING%\desktop" /E /XD __pycache__ /NFL /NDL /NJH /NJS /nc /ns /np >nul

copy /Y "%~dp0backend\requirements.txt" "%STAGING%\backend\requirements.txt" >nul
copy /Y "%~dp0backend\.env.example" "%STAGING%\backend\.env.example" >nul
copy /Y "%~dp0TradePilot.bat" "%STAGING%\TradePilot.bat" >nul
copy /Y "%~dp0Setup-TradePilot.bat" "%STAGING%\Setup-TradePilot.bat" >nul
copy /Y "%~dp0SHARE.txt" "%STAGING%\SHARE.txt" >nul
if exist "%~dp0.gitignore" copy /Y "%~dp0.gitignore" "%STAGING%\.gitignore" >nul

REM Never pack secrets or local runtime state.
if exist "%STAGING%\backend\.env" del /f /q "%STAGING%\backend\.env"
if exist "%STAGING%\backend\desk_state" rmdir /s /q "%STAGING%\backend\desk_state"
if exist "%STAGING%\backend\.venv" rmdir /s /q "%STAGING%\backend\.venv"

echo Creating zip...
powershell -NoProfile -Command ^
  "if (Test-Path -LiteralPath '%ZIP%') { Remove-Item -LiteralPath '%ZIP%' -Force }; Compress-Archive -Path '%STAGING%\*' -DestinationPath '%ZIP%' -Force"

if errorlevel 1 (
  echo ERROR: zip failed.
  rmdir /s /q "%STAGING%"
  pause
  exit /b 1
)

rmdir /s /q "%STAGING%"
echo.
echo Share file ready:
echo   %ZIP%
echo.
echo Give that zip to the other PC. They unzip, run Setup-TradePilot.bat, then TradePilot.bat.
echo Do not include your real backend\.env.
echo.
explorer "%OUTDIR%"
pause
exit /b 0
