# Register (or remove) the Scheduled Task that runs watchdog_system.ps1 as SYSTEM
# every 15 minutes, so the Phase 3 batch resumes after a logoff or a reboot.
#
# MUST BE RUN FROM AN ELEVATED PowerShell -- registering a task that runs as SYSTEM
# needs administrator rights. Running it unelevated fails with "Access is denied".
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1"
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Remove
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Status
#
# Why SYSTEM and not the logged-on user: a task set to "run whether the user is
# logged on or not" under a user account needs that account's stored password (or
# the batch-logon right). SYSTEM needs neither, and E: is a local volume so it has
# the access it needs. Files it creates inherit the folder's NTFS ACL.
#
# Why /SC MINUTE rather than ONSTART: a MINUTE schedule fires regardless of who is
# logged on AND resumes by itself after a reboot, which gives both behaviours with
# one trigger. Worst case after a reboot, the batch restarts within 15 minutes.
#
# The task is safe to fire while the batch is healthy: watchdog_system.ps1 exits
# without acting when the runner is alive, when a worker is still solving, when
# STOP_BATCH exists, or when the batch is complete.

param([switch]$Remove, [switch]$Status)

$taskName = "Phase3BatchWatchdog"
$proj     = $PSScriptRoot
$script   = Join-Path $proj "watchdog_system.ps1"

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$elevated = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if ($Status) {
    schtasks /query /tn $taskName /v /fo LIST 2>&1 | Select-String -Pattern `
        'TaskName|Status|Last Run Time|Last Result|Next Run Time|Run As User|Repeat: Every'
    exit $LASTEXITCODE
}

if (-not $elevated) {
    Write-Error ("Not elevated (running as $($id.Name)). Re-run this from an " +
                 "administrator PowerShell: registering a SYSTEM task requires it.")
    exit 1
}

if ($Remove) {
    schtasks /delete /tn $taskName /f
    exit $LASTEXITCODE
}

if (-not (Test-Path $script)) { Write-Error "missing $script"; exit 1 }

# -NoProfile so a user profile cannot change behaviour; -ExecutionPolicy Bypass
# because the task runs as SYSTEM, whose policy may differ from the user's.
$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""

schtasks /create /tn $taskName /tr $action /sc MINUTE /mo 15 `
         /ru SYSTEM /rl HIGHEST /f
if ($LASTEXITCODE -ne 0) { Write-Error "schtasks /create failed"; exit $LASTEXITCODE }

Write-Host ""
Write-Host "Registered '$taskName': watchdog_system.ps1 as SYSTEM, every 15 minutes."
Write-Host "Kill switch: create a file named STOP_BATCH in the repo root to stop it"
Write-Host "relaunching; delete the file to re-arm. Log: logs\watchdog_system.log"
Write-Host ""
schtasks /run /tn $taskName | Out-Null
Write-Host "Triggered one run now; check the log in a few seconds."
