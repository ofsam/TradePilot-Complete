# Download Windows embeddable Python and install TradePilot deps into it.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime\python"
$Marker = Join-Path $Runtime ".tradepilot_runtime_ok"
$Req = Join-Path $Root "backend\requirements.txt"
$Ver = "3.11.9"
$ZipName = "python-$Ver-embed-amd64.zip"
$Url = "https://www.python.org/ftp/python/$Ver/$ZipName"
$Cache = Join-Path $Root "runtime\cache"
$ZipPath = Join-Path $Cache $ZipName

New-Item -ItemType Directory -Force -Path $Cache | Out-Null

if ((Test-Path $Marker) -and (Test-Path (Join-Path $Runtime "python.exe"))) {
    Write-Host "Runtime already prepared: $Runtime"
    exit 0
}

if (-not (Test-Path $ZipPath)) {
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
}

if (Test-Path $Runtime) {
    Remove-Item -Recurse -Force $Runtime
}
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Expand-Archive -Path $ZipPath -DestinationPath $Runtime -Force

$pth = Get-ChildItem $Runtime -Filter "python*._pth" | Select-Object -First 1
if (-not $pth) { throw "python*._pth not found in embeddable runtime" }
$pthText = @(
    "python311.zip"
    "."
    "Lib\\site-packages"
    "import site"
) -join "`r`n"
Set-Content -Path $pth.FullName -Value $pthText -Encoding ASCII

$getPip = Join-Path $Cache "get-pip.py"
if (-not (Test-Path $getPip)) {
    Write-Host "Downloading get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
}

$py = Join-Path $Runtime "python.exe"
Write-Host "Installing pip into portable runtime..."
& $py $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }

Write-Host "Installing TradePilot requirements into portable runtime..."
& $py -m pip install --upgrade pip
& $py -m pip install -r $Req
if ($LASTEXITCODE -ne 0) { throw "pip install requirements failed" }

# Smoke imports used at launch
& $py -c "import fastapi, uvicorn, dotenv, MetaTrader5; print('runtime_imports_ok')"
if ($LASTEXITCODE -ne 0) { throw "runtime smoke import failed" }

Set-Content -Path $Marker -Value (Get-Date).ToString("o") -Encoding ASCII
Write-Host "Portable runtime ready."
