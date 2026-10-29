<#
 Compile LocalSMS en LocalSMS.exe (PyInstaller). À exécuter SOUS WINDOWS.
 Prérequis : Python 3.10+ (python.org, « Add to PATH ») et Node.js 18+ (nodejs.org).
 Usage :   .\scripts\build_windows.ps1            -> dist\LocalSMS.exe (fichier unique)
           .\scripts\build_windows.ps1 -OneDir    -> dist\LocalSMS\LocalSMS.exe (démarre plus vite)
           .\scripts\build_windows.ps1 -SkipTests
#>
param([switch]$OneDir, [switch]$SkipTests)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd introuvable. $hint" } }
Need python "Installez Python 3.10+ depuis https://www.python.org/downloads/"
Need npm    "Installez Node.js LTS depuis https://nodejs.org/"
python -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ requis'"

Write-Host "==> 1/5 Interface web (React + Vite)" -ForegroundColor Cyan
Push-Location web
if (Test-Path package-lock.json) { npm ci --no-audit --no-fund } else { npm install --no-audit --no-fund }
if ($LASTEXITCODE -ne 0) { throw "npm install a échoué" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "La compilation de l'interface a échoué" }
Pop-Location

Write-Host "==> 2/5 Environnement Python" -ForegroundColor Cyan
if (-not (Test-Path .venv-build)) { python -m venv .venv-build }
$Py = Join-Path $Root ".venv-build\Scripts\python.exe"
& $Py -m pip install --upgrade pip --quiet
& $Py -m pip install -r backend\requirements-dev.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install a échoué" }

if (-not $SkipTests) {
  Write-Host "==> 3/5 Tests" -ForegroundColor Cyan
  Push-Location backend; & $Py -m pytest -q; $code = $LASTEXITCODE; Pop-Location
  if ($code -ne 0) { throw "Des tests ont échoué : compilation annulée" }
}

Write-Host "==> 4/5 PyInstaller" -ForegroundColor Cyan
if (-not (Test-Path scripts\localsms.ico)) { & $Py scripts\make_icon.py }
if ($OneDir) { $env:LOCALSMS_ONEDIR = "1" } else { Remove-Item Env:\LOCALSMS_ONEDIR -ErrorAction SilentlyContinue }
Push-Location backend
& $Py -m PyInstaller localsms.spec --noconfirm --clean --distpath ..\dist --workpath ..\build\pyinstaller
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "PyInstaller a échoué" }

Write-Host "==> 5/5 Vérification" -ForegroundColor Cyan
$Exe = if ($OneDir) { "dist\LocalSMS\LocalSMS.exe" } else { "dist\LocalSMS.exe" }
if (-not (Test-Path $Exe)) { throw "Exécutable introuvable : $Exe" }
$env:LOCALSMS_BIN = (Resolve-Path $Exe).Path
& $Py scripts\e2e_test.py
if ($LASTEXITCODE -ne 0) { throw "Le test de bout en bout de l'exécutable a échoué" }
$hash = (Get-FileHash $Exe -Algorithm SHA256).Hash
Write-Host "`nTerminé : $Exe" -ForegroundColor Green
Write-Host "SHA-256 : $hash"
