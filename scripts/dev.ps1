# Développement sous Windows : API sur :8765 + interface Vite sur :5173.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path backend\.venv)) { python -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements-dev.txt
if (-not (Test-Path web\node_modules)) { Push-Location web; npm install; Pop-Location }
$api = Start-Process -PassThru -WorkingDirectory backend -FilePath ..\backend\.venv\Scripts\python.exe -ArgumentList "-m","localsms","--no-browser"
try {
  Start-Sleep 2
  $token = (Get-Content "$env:LOCALAPPDATA\LocalSMS\admin_token").Trim()
  Write-Host "Interface de dev : http://localhost:5173/#token=$token"
  Push-Location web; npm run dev; Pop-Location
} finally { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
