# Register (or remove) the Scheduled Task that runs watchdog_system.ps1 as SYSTEM
# every 15 minutes, so the Phase 3 batch resumes after a logoff or a reboot.
#
# MUST BE RUN FROM AN ELEVATED PowerShell -- registering a task that runs as SYSTEM
# needs administrator rights. Unelevated it stops with a clear message.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1"
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Remove
#   powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Status
#
# HISTORY -- why this uses Register-ScheduledTask and not schtasks.exe:
# the first version built a command STRING and passed it to `schtasks /create /tr`.
# PowerShell strips one layer of quoting before schtasks ever sees it, so this repo's
# path ("E:\works\Video compression Research\...") split and schtasks reported
#     ERROR: Invalid argument/option - 'compression'.
# That is the THIRD time a space in this path has broken a launch command
# (PHASE3_NOTES.md §2). Register-ScheduledTask takes objects, so the path is never
# re-parsed by a shell: the fix removes the failure mode instead of escaping around it.
#
# Why SYSTEM: a task set to "run whether the user is logged on or not" under a user
# account needs that account's stored password (or the batch-logon right). SYSTEM needs
# neither, and E: is a local volume. Files it creates inherit the folder's NTFS ACL.
#
# Two triggers, deliberately:
#   - AtStartup, so a reboot resumes the batch without waiting on anything else;
#   - Once + 15-minute repetition, for the ordinary watch.
# MultipleInstances=IgnoreNew means a slow run is never joined by a second copy, and
# the 10-minute execution limit means a wedged instance cannot block later ones. The
# watchdog itself is one-shot and normally exits in under a second.

param([switch]$Remove, [switch]$Status)

$taskName = "Phase3BatchWatchdog"
$proj     = $PSScriptRoot
$script   = Join-Path $proj "watchdog_system.ps1"

function Get-Task {
    Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}

if ($Status) {
    $t = Get-Task
    if (-not $t) {
        Write-Host "NOT INSTALLED: no scheduled task named '$taskName'."
        exit 1
    }
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host "TaskName    : $($t.TaskName)"
    Write-Host "State       : $($t.State)"
    Write-Host "RunAs       : $($t.Principal.UserId) ($($t.Principal.RunLevel))"
    Write-Host "Execute     : $($t.Actions[0].Execute)"
    Write-Host "Arguments   : $($t.Actions[0].Arguments)"
    Write-Host "LastRunTime : $($info.LastRunTime)"
    Write-Host "LastResult  : $($info.LastTaskResult)  (0 = success)"
    Write-Host "NextRunTime : $($info.NextRunTime)"
    exit 0
}

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$elevated = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) {
    Write-Error ("Not elevated (running as $($id.Name)). Re-run this from an " +
                 "administrator PowerShell: registering a SYSTEM task requires it.")
    exit 1
}

if ($Remove) {
    if (-not (Get-Task)) { Write-Host "Nothing to remove: '$taskName' is not registered."; exit 0 }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed scheduled task '$taskName'."
    exit 0
}

if (-not (Test-Path -LiteralPath $script)) {
    Write-Error "missing $script"
    exit 1
}

# The only place the path appears. It is quoted for powershell.exe's OWN -File
# parsing, and passed as a single -Argument value, so no shell re-splits it.
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $proj

$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 15))
)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" `
    -LogonType ServiceAccount -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers `
    -Principal $principal -Settings $settings -Force `
    -Description "Relaunches the Phase 3 SS-RTD batch if it stops. Honours the STOP_BATCH sentinel in the repo root. See RESEARCH_LOG.md section 13." | Out-Null

$t = Get-Task
if (-not $t) { Write-Error "registration reported success but the task is not present"; exit 1 }

Write-Host ""
Write-Host "Registered '$taskName' as SYSTEM: AtStartup + every 15 minutes."
Write-Host "  Execute  : $($t.Actions[0].Execute)"
Write-Host "  Arguments: $($t.Actions[0].Arguments)"
Write-Host ""
Write-Host "Kill switch: create a file named STOP_BATCH in the repo root to stop it"
Write-Host "relaunching; delete the file to re-arm. Log: logs\watchdog_system.log"
Write-Host ""
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 5
$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "Triggered one run now. LastResult: $($info.LastTaskResult) (0 = success)"
Write-Host "Check logs\watchdog_system.log for the line it just wrote."
