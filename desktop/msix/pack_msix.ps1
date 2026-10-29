# Packages desktop\dist\BlockTrace into desktop\dist\BlockTrace.msix for the Microsoft Store.
# Run desktop\build.ps1 first. Pass the identity values from Partner Center
# (Product management > Product identity), e.g.:
#   powershell -ExecutionPolicy Bypass -File desktop\msix\pack_msix.ps1 `
#     -IdentityName "12345YourName.BlockTrace" -Publisher "CN=XXXXXXXX-XXXX-..." `
#     -PublisherDisplayName "Your Name" -Version 1.0.0.0
# The Store signs the package on upload, so it is left unsigned here.
param(
    [string]$IdentityName = "AasifAhmedA.BlockTrace",
    [string]$Publisher = "CN=6F455BAC-5AF8-4281-A95D-D1FFC582C602",
    [string]$PublisherDisplayName = "Aasif Ahmed A",
    [string]$Version = "1.0.0.0"
)
$ErrorActionPreference = "Stop"
$MsixDir = $PSScriptRoot
$Desktop = Split-Path $MsixDir -Parent
$AppDir = Join-Path $Desktop "dist\BlockTrace"
$Py = Join-Path $Desktop ".venv\Scripts\python.exe"
if (-not (Test-Path (Join-Path $AppDir "BlockTrace.exe"))) { throw "Run desktop\build.ps1 first" }
if ($Version -notmatch '^\d+\.\d+\.\d+\.0$') { throw "Store versions must look like 1.2.3.0 (last part 0)" }

# 1. makeappx from Microsoft's SDK BuildTools NuGet package (cached in desktop\.tools)
$SdkVersion = "10.0.28000.2270"
$Tools = Join-Path $Desktop ".tools\sdk-buildtools-$SdkVersion"
if (-not (Test-Path $Tools)) {
    $Nupkg = Join-Path $Desktop ".tools\sdk-buildtools.zip"
    New-Item -ItemType Directory -Force (Split-Path $Nupkg) | Out-Null
    Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/$SdkVersion/microsoft.windows.sdk.buildtools.$SdkVersion.nupkg" -OutFile $Nupkg
    Expand-Archive $Nupkg $Tools
    Remove-Item $Nupkg
}
$MakeAppx = Get-ChildItem $Tools -Recurse -Filter makeappx.exe | Where-Object { $_.FullName -match '\\x64\\' } | Select-Object -First 1
if (-not $MakeAppx) { throw "makeappx.exe not found in $Tools" }

# 2. Package layout: manifest + Assets + the PyInstaller app folder
$Layout = Join-Path $Desktop "build\msix-layout"
if (Test-Path $Layout) { Remove-Item -Recurse -Force $Layout }
New-Item -ItemType Directory -Force $Layout | Out-Null
Copy-Item -Recurse $AppDir (Join-Path $Layout "BlockTrace")
& $Py (Join-Path $MsixDir "make_assets.py") (Join-Path $Desktop "web\icons\icon-512.png") (Join-Path $Layout "Assets")
if ($LASTEXITCODE -ne 0) { throw "Asset generation failed" }

$esc = { param($s) [System.Security.SecurityElement]::Escape($s) }
$Manifest = (Get-Content -Raw (Join-Path $MsixDir "AppxManifest.xml")).
    Replace("{{IDENTITY_NAME}}", (& $esc $IdentityName)).
    Replace("{{PUBLISHER}}", (& $esc $Publisher)).
    Replace("{{PUBLISHER_DISPLAY_NAME}}", (& $esc $PublisherDisplayName)).
    Replace("{{VERSION}}", $Version)
[IO.File]::WriteAllText((Join-Path $Layout "AppxManifest.xml"), $Manifest, (New-Object Text.UTF8Encoding $false))

# 3. Pack
$Out = Join-Path $Desktop "dist\BlockTrace.msix"
& $MakeAppx.FullName pack /d $Layout /p $Out /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed" }
Write-Host "`nBuilt: $Out"
