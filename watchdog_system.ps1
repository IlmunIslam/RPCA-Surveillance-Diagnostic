# Phase 3 watchdog that survives a logoff.
#
# Why this exists: the batch was interrupted twice in three days -- once by Modern
# Standby (RESEARCH_LOG.md section 12) and once by a logoff whose window-station
# shutdown killed the worker, the runner AND watchdog_phase3.ps1 together, leaving
# the batch idle and unnoticed for 18 hours (section 13). A user-session watchdog
# cannot survive that event, because it dies in it. This script is meant to be run
# by a Scheduled Task as SYSTEM every 15 minutes, which survives logoff and resumes
# after a reboot.
#
# It is one shot per invocation: check, act if needed, exit. The Scheduled Task
# provides the schedule; see install_watchdog_task.ps1.
#
# Differences from watchdog_phase3.ps1 (which stays, for foreground use):
#  - no polling loop, no lifetime -- the task schedules it;
#  - a STOP_BATCH kill switch, checked BEFORE every relaunch;
#  - state kept in a file rather than in memory, since each run is a new process.
#
# Safety: it never starts a second writer. The runner holds results/ssrtd_real/
# runner.lock with its pid and refuses to start while that pid is alive, and this
# script additionally waits while a worker is still solving.
#
#   -DryRun   decide and log, but never launch anything. Used to test the logic.

param([switch]$DryRun)

$proj      = $PSScriptRoot
$csv       = Join-Path $proj "results\metrics\ssrtd_real_results.csv"
$planCsv   = Join-Path $proj "results\ssrtd_real\plan.csv"
$wlog      = Join-Path $proj "logs\watchdog_system.log"
$stopFile  = Join-Path $proj "STOP_BATCH"
$stateFile = Join-Path $proj "logs\watchdog_state.json"
$maxStall  = 4           # refuse further relaunches after this many with no new rows
$heartbeat = 6           # hours: re-log an unchanged state at least this often

function Log($m) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $tag = if ($DryRun) { "[dry] " } else { "" }
    Add-Content -Path $wlog -Value "$ts  $tag$m"
}

function Get-RowCount($path) {
    if (Test-Path $path) {
        $n = (Get-Content $path | Measure-Object -Line).Lines - 1   # minus header
        if ($n -lt 0) { return 0 }
        return $n
    }
    return 0
}

function Get-Proc($pattern) {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match $pattern } |
        Select-Object -First 1
}

function Read-State {
    if (Test-Path $stateFile) {
        try { return Get-Content $stateFile -Raw | ConvertFrom-Json } catch { }
    }
    return [pscustomobject]@{ state = ""; rows = 0; relaunches = 0; lastLog = "" }
}

function Write-State($state, $rows, $relaunches, $lastLog) {
    [pscustomobject]@{
        state = $state; rows = $rows; relaunches = $relaunches; lastLog = $lastLog
    } | ConvertTo-Json | Set-Content -Path $stateFile -Encoding utf8
}

# Log a state only when it changes, or every $heartbeat hours, so a quiet watch does
# not write 96 lines a day. A state's FIRST occurrence is always logged.
function Log-State($st, $msg, $prev) {
    $now = Get-Date
    $due = $true
    if ($prev.state -eq $st -and $prev.lastLog) {
        try { $due = ($now - [datetime]$prev.lastLog).TotalHours -ge $heartbeat } catch { }
    }
    if ($due) { Log $msg; return $now.ToString('o') }
    return $prev.lastLog
}

if (-not (Test-Path (Join-Path $proj "logs"))) {
    New-Item -ItemType Directory -Force (Join-Path $proj "logs") | Out-Null
}

$prev = Read-State
$rows = Get-RowCount $csv

# ---- 1. kill switch, before anything else -------------------------------------
if (Test-Path $stopFile) {
    $lastLog = Log-State "stopped" "STOP_BATCH present -- not relaunching ($rows rows)" $prev
    Write-State "stopped" $rows $prev.relaunches $lastLog
    exit 0
}

# ---- 2. is the batch finished? -------------------------------------------------
$target = Get-RowCount $planCsv
if ($target -le 0) {
    $lastLog = Log-State "noplan" "no plan.csv yet -- waiting rather than guessing" $prev
    Write-State "noplan" $rows $prev.relaunches $lastLog
    exit 0
}
if ($rows -ge $target) {
    $lastLog = Log-State "done" "batch complete: $rows of $target rows" $prev
    Write-State "done" $rows $prev.relaunches $lastLog
    exit 0
}

# ---- 3. already running? -------------------------------------------------------
$runner = Get-Proc 'src\.phase3_runner'
if ($runner) {
    $lastLog = Log-State "running" "runner alive (pid $($runner.ProcessId)), $rows/$target rows" $prev
    Write-State "running" $rows 0 $lastLog     # progress resets the stall counter
    exit 0
}

# A worker without a runner means the runner died mid-run. Let the worker finish:
# it writes summary.json last, and the next runner ADOPTS that row instead of
# recomputing it. Relaunching now would put two solvers in 2.8 GB-peak each.
$worker = Get-Proc 'src\.phase3_worker'
if ($worker) {
    $lastLog = Log-State "orphan" "runner gone but worker (pid $($worker.ProcessId)) still solving -- waiting" $prev
    Write-State "orphan" $rows $prev.relaunches $lastLog
    exit 0
}

# ---- 4. stall protection -------------------------------------------------------
# Count relaunches that produced no new rows. Without this a SYSTEM task would
# resurrect a permanently broken batch every 15 minutes, forever.
$relaunches = [int]$prev.relaunches
if ($rows -le [int]$prev.rows -and $prev.state -eq "relaunched") {
    $relaunches++
} elseif ($rows -gt [int]$prev.rows) {
    $relaunches = 0
}
if ($relaunches -ge $maxStall) {
    $lastLog = Log-State "gaveup" ("no new rows across $relaunches consecutive " +
        "relaunch checks -- refusing further relaunches. Fix the cause, then " +
        "delete logs\watchdog_state.json to re-arm.") $prev
    Write-State "gaveup" $rows $relaunches $lastLog
    exit 0
}

# ---- 5. relaunch ---------------------------------------------------------------
if ($DryRun) {
    Log "WOULD relaunch the runner now ($rows/$target rows, relaunch #$($relaunches + 1))"
    Write-State $prev.state $rows $prev.relaunches $prev.lastLog   # dry run changes nothing
    exit 0
}

# Resolve python to an ABSOLUTE path. Under SYSTEM, bare "python" is not found:
# this machine's interpreter is a per-user install on ilmun's PATH, and SYSTEM has
# neither that PATH nor a useful $env:LOCALAPPDATA. The first real firing of this
# branch (2026-11-03 00:07) logged "relaunching" twice while cmd answered
# "'python' is not recognized" -- see RESEARCH_LOG.md section 16.
# ffmpeg needs no equivalent: src/compression.py already falls back to its absolute
# WinGet path when shutil.which fails.
$pythonExe = $env:PHASE3_PYTHON
if (-not $pythonExe) {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source   # as the user
}
if (-not $pythonExe) {
    $pythonExe = "C:\Users\ilmun\AppData\Local\Programs\Python\Python312\python.exe"
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    # Do NOT claim a relaunch we cannot perform, and do not burn a stall count on it.
    $lastLog = Log-State "nopython" ("cannot relaunch: no python at '$pythonExe'. Set " +
        "PHASE3_PYTHON to the interpreter's full path, then delete " +
        "logs\watchdog_state.json.") $prev
    Write-State "nopython" $rows $prev.relaunches $lastLog
    exit 1
}

# Give the child the interpreter's own directory on PATH too, so anything inside the
# batch that shells out to "python" resolves the same one.
$env:PATH = (Split-Path $pythonExe) + ";" + $env:PATH

Log "runner not running and batch incomplete ($rows/$target) -- relaunching (#$($relaunches + 1)) with $pythonExe"
Start-Process -FilePath cmd.exe `
  -ArgumentList '/c', "`"$pythonExe`" -u -m src.phase3_runner >> logs\phase3_runner.stdout.log 2>&1" `
  -WorkingDirectory $proj -WindowStyle Hidden

# Verify the relaunch actually took. A watchdog that logs a success it did not achieve
# is the guardrail-that-reports-itself-active problem in its own log.
$started = $null
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 2
    $started = Get-Proc 'src\.phase3_runner'
    if ($started) { break }
}
if ($started) {
    Log "relaunch took: runner pid $($started.ProcessId)"
    Write-State "relaunched" $rows $relaunches (Get-Date).ToString('o')
    exit 0
}

$tail = ""
$outLog = Join-Path $proj "logs\phase3_runner.stdout.log"
if (Test-Path $outLog) { $tail = (Get-Content $outLog -Tail 3) -join " / " }
Log "relaunch did NOT take after 20s -- stdout tail: $tail"
Write-State "launchfail" $rows ($relaunches + 1) (Get-Date).ToString('o')
exit 1
