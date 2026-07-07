# Watchdog for the SS-RTD parameter sweep.
# Keeps `python -u -m src.param_sweep` alive across harness reaping / crashes.
# - Polls every 60s.
# - If no param_sweep process is running and the sweep isn't complete, relaunches it detached.
# - Exits cleanly once param_sweep.csv holds all TARGET rows.
# - Gives up (no crash-loop) if repeated relaunches make no progress.
# Launch this itself detached:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
#     'S:\works\Video compression Research\RPCA_Hybrid_Project\watchdog_param_sweep.ps1' -WindowStyle Hidden

$proj   = "S:\works\Video compression Research\RPCA_Hybrid_Project"
$csv    = Join-Path $proj "results\metrics\param_sweep.csv"
$wlog   = Join-Path $proj "logs\watchdog.log"
$target = 100          # 20 videos x 5 configs
$maxStall = 4          # give up after this many relaunches with no new rows

function Log($m) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $wlog -Value "$ts  $m"
}

function Get-RowCount {
    if (Test-Path $csv) {
        $n = (Get-Content $csv | Measure-Object -Line).Lines - 1   # minus header
        if ($n -lt 0) { return 0 }
        return $n
    }
    return 0
}

function Get-SweepProc {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'src\.param_sweep' } |
        Select-Object -First 1
}

Log "watchdog started (pid $PID); target=$target rows"

$stall    = 0
$lastRows = -1

while ($true) {
    $rows = Get-RowCount
    if ($rows -ge $target) {
        Log "sweep complete ($rows/$target rows) - watchdog exiting"
        break
    }

    $proc = Get-SweepProc
    if (-not $proc) {
        # Sweep is down. Decide whether it's making progress across deaths.
        if ($rows -le $lastRows) { $stall++ } else { $stall = 0 }
        $lastRows = $rows

        if ($stall -ge $maxStall) {
            Log "ERROR: $stall relaunches with no new rows (stuck at $rows/$target) - giving up"
            break
        }

        Log "sweep not running ($rows/$target rows) - relaunching detached (stall=$stall)"
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList '/c','python -u -m src.param_sweep >> logs\param_sweep.log 2>&1' `
            -WorkingDirectory $proj -WindowStyle Hidden
        Start-Sleep -Seconds 8
        $p2 = Get-SweepProc
        if ($p2) { Log "relaunched OK (pid $($p2.ProcessId))" }
        else     { Log "WARN: relaunch not detected after 8s" }
    }

    Start-Sleep -Seconds 60
}
