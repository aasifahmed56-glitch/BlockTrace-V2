# Builds the BlockTrace desktop app into desktop\dist\BlockTrace\BlockTrace.exe
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File desktop\build.ps1
$ErrorActionPreference = "Stop"
$Desktop = $PSScriptRoot
$Root = Split-Path $Desktop -Parent
$Frontend = Join-Path $Root "stitch_universal_build_framework"

# 1. Frontend, with API calls routed through the app's local /api proxy
Push-Location $Frontend
$env:VITE_API_BASE_URL = "/api"
npx vite build --outDir ../desktop/web --emptyOutDir
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Remove-Item Env:VITE_API_BASE_URL
Pop-Location

# 2. Isolated build venv (keeps backend packages like web3/neo4j out of the exe)
$Venv = Join-Path $Desktop ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    $BasePy = Join-Path $Root "venv\Scripts\python.exe"
    if (-not (Test-Path $BasePy)) { $BasePy = "python" }
    & $BasePy -m venv $Venv
}
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r (Join-Path $Desktop "requirements-desktop.txt")

# 3. App icon from the PWA icon
New-Item -ItemType Directory -Force (Join-Path $Desktop "assets") | Out-Null
& $Py -c "from PIL import Image; Image.open(r'$Desktop\web\icons\icon-512.png').save(r'$Desktop\assets\BlockTrace.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

# 4. Package
Push-Location $Desktop
& $Py -m PyInstaller --noconfirm --clean BlockTrace.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Pop-Location

Write-Host "`nBuilt: $Desktop\dist\BlockTrace\BlockTrace.exe"
