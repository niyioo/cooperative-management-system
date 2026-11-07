# Replaces everything in the system with a backup: after a computer failure,
# when moving to a new computer, or to bring records over from another installation.
#   powershell -ExecutionPolicy Bypass -File restore.ps1 -Dump D:\EMDI-backups\emdi_2026-11-03_1900.dump [-Media D:\EMDI-backups\media_2026-11-03_1900.tgz]
param(
    [Parameter(Mandatory = $true)][string]$Dump,
    [string]$Media,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path $Dump)) { throw "No such file: $Dump" }
if ($Media -and -not (Test-Path $Media)) { throw "No such file: $Media" }

function Read-Env([string]$Key, [string]$Default) {
    $line = Get-Content .env | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if ($line) { $value = $line.Substring($Key.Length + 1).Trim(); if ($value) { return $value } }
    return $Default
}
function Set-Env([string]$Key, [string]$Value) {
    $lines = @(Get-Content .env | Where-Object { $_ -notmatch "^$Key=" }) + "$Key=$Value"
    $lines | Set-Content -Encoding ascii .env
}
function Check([string]$What) { if ($LASTEXITCODE -ne 0) { throw "$What failed" } }

if (-not $Yes) {
    $answer = Read-Host "This replaces ALL records in the system with $(Split-Path -Leaf $Dump). Type RESTORE to continue"
    if ($answer -ne "RESTORE") { Write-Host "Nothing changed."; exit 1 }
}

$user = Read-Env "DB_USER" "emdi_coop"
$db = Read-Env "DB_NAME" "emdi_coop"

docker compose stop backend; Check "stopping the backend"
docker compose cp $Dump db:/tmp/restore.dump; Check "copying the backup in"
docker compose exec -T db dropdb -U $user --force --if-exists $db; Check "clearing the database"
docker compose exec -T db createdb -U $user -O $user $db; Check "creating the database"
docker compose exec -T db pg_restore -U $user -d $db --no-owner --no-privileges /tmp/restore.dump; Check "restoring"
docker compose exec -T db rm -f /tmp/restore.dump

# Records brought from another installation may live in their own schema.
$schema = "$(docker compose exec -T db psql -U $user -d $db -tAc "select table_schema from information_schema.tables where table_name = 'django_migrations' order by table_schema = 'public' desc limit 1")".Trim()
if (-not $schema) { throw "The backup does not contain the system's tables." }
if ($schema -eq "public") { Set-Env "DB_SCHEMA" "" } else { Set-Env "DB_SCHEMA" $schema }
Write-Host "Records are in the '$schema' schema."

# Recreated so it picks up DB_SCHEMA, then brought up to date with any newer migrations.
docker compose up -d --force-recreate backend; Check "starting the backend"

if ($Media) {
    docker compose cp $Media backend:/tmp/media.tgz; Check "copying the documents in"
    docker compose exec -T backend sh -c "rm -rf /app/media/* && tar -xzf /tmp/media.tgz -C /app && rm -f /tmp/media.tgz"; Check "unpacking the documents"
}
Write-Host "Restore complete."
