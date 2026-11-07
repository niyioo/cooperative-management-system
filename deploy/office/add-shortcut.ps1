# Puts an "EMDI Cooperative" icon on the desktop that opens the system in its own
# window, like an installed app. setup.ps1 runs it on the office computer; run it
# on each official's laptop too, naming the office computer:
#   powershell -ExecutionPolicy Bypass -File add-shortcut.ps1 -Server emdi-office
param([string]$Server = "localhost", [int]$Port = 80)

$ErrorActionPreference = "Stop"
$address = "http://$Server$(if ($Port -ne 80) { ":$Port" })/"

# The icon is kept on this computer, so the shortcut still works once the
# installation files (or the flash drive) are gone.
$home_ = Join-Path $env:LOCALAPPDATA "EMDI"
New-Item -ItemType Directory -Force $home_ | Out-Null
$icon = Join-Path $home_ "emdi.ico"
Copy-Item (Join-Path $PSScriptRoot "emdi.ico") $icon -Force

$edge = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop "EMDI Cooperative.lnk"))
if ($edge) {
    # Edge's app mode: a window of its own, no address bar or tabs.
    $shortcut.TargetPath = $edge
    $shortcut.Arguments = "--app=$address"
} else {
    $shortcut.TargetPath = $address
}
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = "EMDI Cooperative Multipurpose Society Ltd"
$shortcut.Save()
Write-Host "Added 'EMDI Cooperative' to the desktop ($address)."
