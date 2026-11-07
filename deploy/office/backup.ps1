# Copies the database and uploaded documents to the backup drive, keeping the
# last 30 backups. Runs every evening once schedule-backup.ps1 has been run.
#   powershell -ExecutionPolicy Bypass -File backup.ps1 [-BackupDir E:\EMDI-backups]
param([string]$BackupDir)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Read-Env([string]$Key, [string]$Default) {
    $line = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if ($line) { $value = $line.Substring($Key.Length + 1).Trim(); if ($value) { return $value } }
    return $Default
}

if (-not $BackupDir) { $BackupDir = Read-Env "BACKUP_DIR" "D:\EMDI-backups" }
$drive = Split-Path -Qualifier $BackupDir
if (-not (Test-Path "$drive\")) { throw "The backup drive $drive is not plugged in." }
New-Item -ItemType Directory -Force $BackupDir | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$user = Read-Env "DB_USER" "emdi_coop"
$db = Read-Env "DB_NAME" "emdi_coop"
$log = Join-Path $BackupDir "backup-log.txt"

try {
    # Dumped inside the containers and copied out, so the files stay byte-for-byte.
    docker compose exec -T db pg_dump -U $user -d $db -Fc -f /tmp/emdi.dump
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
    docker compose cp db:/tmp/emdi.dump (Join-Path $BackupDir "emdi_$stamp.dump")
    if ($LASTEXITCODE -ne 0) { throw "copying the database out failed" }
    docker compose exec -T db rm -f /tmp/emdi.dump

    docker compose exec -T backend tar -czf /tmp/media.tgz -C /app media
    if ($LASTEXITCODE -ne 0) { throw "packing the documents failed" }
    docker compose cp backend:/tmp/media.tgz (Join-Path $BackupDir "media_$stamp.tgz")
    if ($LASTEXITCODE -ne 0) { throw "copying the documents out failed" }
    docker compose exec -T backend rm -f /tmp/media.tgz

    foreach ($pattern in "emdi_*.dump", "media_*.tgz") {
        Get-ChildItem $BackupDir -Filter $pattern | Sort-Object Name -Descending | Select-Object -Skip 30 | Remove-Item
    }
    $size = [math]::Round((Get-Item (Join-Path $BackupDir "emdi_$stamp.dump")).Length / 1MB, 1)
    Add-Content $log "$stamp OK database $size MB"
    Write-Host "Backup saved in $BackupDir ($stamp)."
} catch {
    Add-Content $log "$stamp FAILED $($_.Exception.Message)"
    throw
}
