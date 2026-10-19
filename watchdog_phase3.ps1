# Watchdog for the Phase 3 batch (real SS-RTD on VIRAT).
# Adapted from watchdog_param_sweep.ps1; same structure, three things changed:
# the process it looks for, where the target row count comes from, and the relaunch
# command.
# - Polls every 60s.
# - If no phase3_runner process is running and the batch isn't complete, relaunches
#   it detached. The runner is resumable and skips completed runs, so a relaunch
#   never redoes finished work.
# - Target = row count of results/ssrtd_real/plan.csv (minus header), written by the
#   runner at first start. Until it exists, the watchdog waits rather than guessing.
# - Exits cleanly once the results CSV holds that many rows.
# - Gives up (no crash-loop) if repeated relaunches make no progress.
# Launch this itself detached, arguments as ONE quoted string (the repo path has
# spaces; given as an array, -ArgumentList drops it). See PHASE3_NOTES.md.
#   Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"E:\works\Video compression Research\RPCA_Surveillance_Diagnostic\watchdog_phase3.ps1`"" -WindowStyle Hidden

# Resolve the project root from this script's own location, so the watchdog keeps
# working if the repo is moved or the folder renamed.
$proj     = $PSScriptRoot
$csv      = Join-Path $proj "results\metrics\ssrtd_real_results.csv"
$planCsv  = Join-Path $proj "results\ssrtd_real\plan.csv"
$wlog     = Join-Path $proj "logs\watchdog_phase3.log"
$maxStall = 4          # give up after this many relaunches with no new rows

function Log($m) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $wlog -Value "$ts  $m"
}

function Get-RowCount($path) {
    if (Test-Path $path) {
        $n = (Get-Content $path | Measure-Object -Line).Lines - 1   # minus header
        if ($n -lt 0) { return 0 }
        return $n
    }
    return 0
}

function Get-RunnerProc {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'src\.phase3_runner' } |
        Select-Object -First 1
}

function Get-WorkerProc {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'src\.phase3_worker' } |
        Select-Object -First 1
}

Log "watchdog started (pid $PID)"

$stall    = 0
$lastRows = -1

while ($true) {
    $target = Get-RowCount $planCsv
    $rows   = Get-RowCount $csv

    if ($target -le 0) {
        Log "plan.csv not written yet - waiting (runner writes it at first start)"
        Start-Sleep -Seconds 60
        continue
    }

    if ($rows -ge $target) {
        Log "batch complete ($rows/$target rows) - watchdog exiting"
        break
    }

    $proc = Get-RunnerProc
    if (-not $proc) {
        # A worker can outlive its runner if the runner was killed mid-run. Give the
        # worker time to finish rather than starting a second writer alongside it.
        $worker = Get-WorkerProc
        if ($worker) {
            Log "runner down but worker pid $($worker.ProcessId) still solving - waiting"
            Start-Sleep -Seconds 60
            continue
        }

        if ($rows -le $lastRows) { $stall++ } else { $stall = 0 }
        $lastRows = $rows

        if ($stall -ge $maxStall) {
            Log "ERROR: $stall relaunches with no new rows (stuck at $rows/$target) - giving up"
            break
        }

        Log "runner not running ($rows/$target rows) - relaunching detached (stall=$stall)"
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList '/c','python -u -m src.phase3_runner >> logs\phase3_runner.stdout.log 2>&1' `
            -WorkingDirectory $proj -WindowStyle Hidden
        Start-Sleep -Seconds 10
        $p2 = Get-RunnerProc
        if ($p2) { Log "relaunched OK (pid $($p2.ProcessId))" }
        else     { Log "WARN: relaunch not detected after 10s" }
    }

    Start-Sleep -Seconds 60
}
