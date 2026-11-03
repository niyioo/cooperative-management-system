# Sets Windows to run backup.ps1 every evening (and at the next sign-in if the
# computer was off at that time). Run once, from this folder.
#   powershell -ExecutionPolicy Bypass -File schedule-backup.ps1 [-At 19:00]
param([string]$At = "19:00")

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "backup.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "EMDI nightly backup" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Backs up the EMDI cooperative system to the backup drive." -Force | Out-Null
Write-Host "Backups will run every day at $At. Check backup-log.txt on the backup drive."
