# Installs a new version: backs up first, then rebuilds and restarts. Copy the
# new version's files over this folder (keeping .env) before running it.
#   powershell -ExecutionPolicy Bypass -File update.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& (Join-Path $PSScriptRoot "backup.ps1")
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "The update failed. The backup above can be restored with restore.ps1." }
Write-Host "Updated. Database changes are applied as the backend starts."
