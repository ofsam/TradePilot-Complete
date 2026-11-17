@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Usage:
REM   Make-FullPackage.bat
REM   Make-FullPackage.bat with-env     ^(includes your backend\.env for YOUR other PCs^)

set "WITH_ENV=0"
if /I "%~1"=="with-env" set "WITH_ENV=1"

echo.
echo === Building TradePilot Full Package ===
echo.

if not exist "frontend\dist\index.html" (
  echo ERROR: frontend\dist\index.html missing.
  pause
  exit /b 1
)
if not exist "backend\_recover\pyc_backup" (
  echo ERROR: backend\_recover\pyc_backup missing.
  pause
  exit /b 1
)

echo [1/4] Preparing portable Python runtime + dependencies...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\prepare_runtime.ps1"
if errorlevel 1 (
  echo ERROR: runtime prepare failed.
  pause
  exit /b 1
)

set "STAGING=%TEMP%\TradePilot-Full-%RANDOM%"
set "OUTDIR=%~dp0share"
set "ZIP=%OUTDIR%\TradePilot-Full-Portable.zip"

echo [2/4] Staging files...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%" || exit /b 1
mkdir "%OUTDIR%" 2>nul

robocopy "%~dp0backend\app" "%STAGING%\backend\app" /E /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0backend\_recover\pyc_backup" "%STAGING%\backend\_recover\pyc_backup" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0frontend\dist" "%STAGING%\frontend\dist" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0desktop" "%STAGING%\desktop" /E /XD __pycache__ /NFL /NDL /NJH /NJS /nc /ns /np >nul
robocopy "%~dp0runtime\python" "%STAGING%\runtime\python" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul

copy /Y "%~dp0backend\requirements.txt" "%STAGING%\backend\requirements.txt" >nul
copy /Y "%~dp0backend\.env.example" "%STAGING%\backend\.env.example" >nul
copy /Y "%~dp0TradePilot.bat" "%STAGING%\TradePilot.bat" >nul
copy /Y "%~dp0Setup-TradePilot.bat" "%STAGING%\Setup-TradePilot.bat" >nul
copy /Y "%~dp0SHARE.txt" "%STAGING%\SHARE.txt" >nul
copy /Y "%~dp0START-HERE.txt" "%STAGING%\START-HERE.txt" >nul 2>nul

if "%WITH_ENV%"=="1" (
  if exist "%~dp0backend\.env" (
    copy /Y "%~dp0backend\.env" "%STAGING%\backend\.env" >nul
    echo Included backend\.env ^(personal package - do not post publicly^)
  ) else (
    echo WARNING: with-env requested but backend\.env was missing.
  )
) else (
  echo Not including backend\.env. Use: Make-FullPackage.bat with-env
)

echo [3/4] Creating zip...
powershell -NoProfile -Command ^
  "if (Test-Path -LiteralPath '%ZIP%') { Remove-Item -LiteralPath '%ZIP%' -Force }; Compress-Archive -Path '%STAGING%\*' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
  echo ERROR: zip failed.
  rmdir /s /q "%STAGING%"
  pause
  exit /b 1
)

rmdir /s /q "%STAGING%"

echo [4/4] Done.
for %%I in ("%ZIP%") do echo Package: %%~fI  ^(%%~zI bytes^)
echo.
echo On the other PC:
echo  1. Unzip
echo  2. Open START-HERE.txt
echo  3. Double-click TradePilot.bat
echo  4. MetaTrader 5 must be installed and logged in
if "%WITH_ENV%"=="0" echo  5. Copy/edit backend\.env ^(DATABASE_URL^) or rebuild with: Make-FullPackage.bat with-env
echo.
explorer "%OUTDIR%"
pause
exit /b 0
