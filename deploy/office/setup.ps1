# First-time setup on the office computer: writes .env with new secrets and this
# computer's network name, then builds and starts the system.
# Run from this folder:  powershell -ExecutionPolicy Bypass -File setup.ps1
param([int]$Port = 80)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function New-Secret([int]$Length) {
    $chars = [char[]]"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    $bytes = New-Object byte[] $Length
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not running. Start it, wait for 'Engine running', then run this again." }

if (Test-Path .env) {
    Write-Host ".env already exists; keeping its secrets."
} else {
    $name = $env:COMPUTERNAME.ToLower()
    $ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.InterfaceAlias -notlike "vEthernet*" } |
        ForEach-Object { $_.IPAddress })
    $suffix = ""
    if ($Port -ne 80) { $suffix = ":$Port" }
    $hosts = @("localhost", "127.0.0.1", $name) + $ips
    $origins = $hosts | ForEach-Object { "http://$_$suffix" }
    @(
        "# Written by setup.ps1 on $(Get-Date -Format 'yyyy-MM-dd'). Keep this file private: it holds the passwords."
        "SECRET_KEY=$(New-Secret 60)"
        "DB_PASSWORD=$(New-Secret 32)"
        "WEB_PORT=$Port"
        "ALLOWED_HOSTS=$($hosts -join ',')"
        "SITE_ORIGINS=$($origins -join ',')"
        "FRONTEND_URL=http://$name$suffix/#"
        "DB_SCHEMA="
        "BACKUP_DIR=D:\EMDI-backups"
        "# Sign-in emails (optional): a Gmail address and its app password."
        "EMAIL_HOST=smtp.gmail.com"
        "EMAIL_HOST_USER="
        "EMAIL_HOST_PASSWORD="
        "DEFAULT_FROM_EMAIL=EMDI Cooperative <no-reply@localhost>"
    ) | Set-Content -Encoding ascii .env
    Write-Host "Wrote .env for $name ($($ips -join ', '))."
}

Write-Host "Building and starting (the first time takes several minutes)..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose failed; see the messages above." }

$url = "http://localhost$(if ($Port -ne 80) { ":$Port" })/api/v1/public/departments/"
for ($i = 0; $i -lt 60; $i++) {
    try {
        if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $url).StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Seconds 5
}
if ($i -ge 60) { throw "The system did not answer. Check:  docker compose logs backend" }

& (Join-Path $PSScriptRoot "add-shortcut.ps1") -Port $Port

$name = $env:COMPUTERNAME.ToLower()
Write-Host ""
Write-Host "The system is running."
Write-Host "  On this computer:        http://localhost$(if ($Port -ne 80) { ":$Port" })"
Write-Host "  On the office network:   http://$name$(if ($Port -ne 80) { ":$Port" })"
Write-Host "  For a desktop icon on another laptop:  add-shortcut.ps1 -Server $name$(if ($Port -ne 80) { " -Port $Port" })"
