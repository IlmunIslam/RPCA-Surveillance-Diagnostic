# PHASE 3 NOTES — running long batches on this machine

> Lessons from running the original 180-video batch (~75 h, June 2026) and the 100-run
> parameter sweep (~15 h, July 2026). Recovered 2026-09-17 from Claude Code auto-memory
> notes stored under the project's old `S:` path, which no session had loaded since the
> project moved to `E:`. Committed here so a fresh session inherits them.
> **Read this before launching the Phase 3 VIRAT run.**

## 1. Launch long runs fully detached — the harness kills background tasks

**What happened (2026-07-03):** jobs launched with Claude Code's Bash `run_in_background`
(for example `python -u -m src.param_sweep`) were killed about **50 minutes in**,
repeatedly. It was investigated, and ruled out:

- not a Windows out-of-memory kill — no `Resource-Exhaustion-Detector` events in the
  System log;
- not a Python crash — no Application Error or Hang events, and the log stopped cleanly
  mid-iteration with no traceback;
- not sleep — sleep is disabled on AC power.  ⚠️ **Partly falsified 2026-10-20:** Modern Standby (connected standby) is a
  separate mechanism from the sleep that is disabled here, and it DID fire --
  Kernel-Power 506/507 suspended a run for ~92 min (`RESEARCH_LOG.md` §12).
  The per-run timeout does not catch it, since parent and child are suspended
  together, so it bounds active time only. `powercfg /change standby-timeout-ac 0`
  is the preventive setting.

Conclusion: **the harness reaps its own background-task wrapper and takes the child
Python process with it.**

The (g2) Candela gate ran for 30 minutes under `run_in_background` on 2026-09-13 and
finished, which fits a limit of about 50 minutes. Phase 3 is roughly 30-40 minutes per
video and about 90 hours in total, so it must be detached. The limit may have changed
since July; don't rely on it either way.

**How to launch** — from PowerShell, fully detached so the harness can't reap it:

```powershell
Start-Process -FilePath cmd.exe `
  -ArgumentList '/c','python -u -m src.<runner> >> logs\<runner>.log 2>&1' `
  -WorkingDirectory "E:\works\Video compression Research\RPCA_Surveillance_Diagnostic" `
  -WindowStyle Hidden
```

**Plan for the consequences:**

- A detached process is **not a harness-tracked task**, so no completion notification
  arrives. Monitor it by polling the results CSV and the log.
- **Never run two writers against the same results CSV** — the append is not
  concurrency-safe. Before relaunching, confirm no copy is still running, and kill it if
  one is.

### The watchdog

`watchdog_param_sweep.ps1` (repo root) kept the parameter sweep alive. It polls every 60
seconds, relaunches the job detached if no matching Python process is running, exits once
the CSV has all its rows, and gives up after 4 relaunches that add no new rows. It logs to
`logs/watchdog.log`. Verified 2026-07-03 by killing the sweep: the watchdog relaunched it
within one poll cycle. Across the whole ~15-hour sweep, only one relaunch was needed.

It is hard-wired to the sweep (`src.param_sweep`, `param_sweep.csv`, 100 rows).
**Phase 3 needs a copy adapted to the new runner, its output file and its row count.**
Launch the watchdog itself detached as well:

```powershell
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"E:\works\Video compression Research\RPCA_Surveillance_Diagnostic\watchdog_param_sweep.ps1`"" -WindowStyle Hidden
```

**Two gotchas:**

- **`Start-Process -ArgumentList` given as an array drops a script path that contains
  spaces.** Our path contains spaces (`Video compression Research`), so pass the arguments
  as **one quoted string**, as above. The launch example in the comment at the top of
  `watchdog_param_sweep.ps1` used the array form until 2026-09-17; it has been corrected.
- **When checking whether a watchdog is already running**, match
  `-File.*watchdog_param_sweep` and exclude the current shell's `$PID`. A bare
  `-match 'watchdog_param_sweep'` also matches the shell doing the checking.

## 2. Smoke-test every changed code path before a multi-hour batch

**What happened (June 2026):** `save_figure_components()`, which imports matplotlib, was
added and the ~75-hour batch launched without running it once. matplotlib was listed in
`requirements.txt` but was **not installed** in the active Python. The three videos that
save figures (video_01, 101 and 108) each crashed after saving their arrays but **before
writing their CSV row** — silently losing exactly the rows that mattered, hours apart.

**Rules:**

1. **After editing the pipeline, run the changed branch once on one video** before the
   batch. For a new dependency, at least run `python -c "import x"`.
2. **Write the scientific output first, and keep plotting and other optional side effects
   in try/except**, so a figure failure can never drop a result. `src/gate_candela.py`
   already follows this order.
3. **The active environment is the global Python 3.12, and it does not have everything in
   `requirements.txt`.** Known missing as of 2026-09: `pytest`, `psutil`, `requests`.
   Check imports rather than assuming.

## 3. Make the runner resumable — and key it on the NEW results file

`src/batch_runner.py` ran the original batch one video at a time through
`src/run_pipeline.py` and was **resumable**: it skips any `video_id` already in the
results CSV, so after an interruption you simply re-run it. In practice the interruptions
were **power loss and the laptop shutting down**, not session problems. Only the
in-progress video was lost, and nothing was corrupted. The per-video timeout was 3600 s;
timeouts were logged to `logs/batch_errors.log`, and progress to `logs/batch_run.log`.

For Phase 3:

- **Keep the resumable design, but make the skip check read the new output file**,
  `results/metrics/ssrtd_real_results.csv` (per the output contract in
  `IMPLEMENTATION_PLAN.md`). ⚠️ Pointed at `all_results.csv`, it would find all 180
  baseline rows and skip every video.
- **Revisit the 3600 s per-video timeout.** Measured 2026-09-19 after the memory
  work: **~22 min per video** at 100 iterations (`RESEARCH_LOG.md` §7.7), before the
  H.264 step; no iteration above 18 s. (Before the allocation levers it was 35.9 min
  with iterations spiking to 48 s while the machine paged — that is what a
  memory-starved run looks like in the log.) Budget the H.264 step before setting
  the timeout.
- **Memory is the other constraint — measured, not projected.** This machine has
  **7.8 GB** of RAM (⚠️ wrong — measured 15.8 GB at the
  2026-10-19 launch; see the correction at the end of this section). The full-loop peak is **2,663 MB** per video after the `rfftn`
  change and levers A–E (`RESEARCH_LOG.md` §7.5–§7.7), down from 3,512 MB, at which
  the machine paged (commit charge 93%). Headroom is now roughly 2 GB. Close other
  programs during the run regardless; if iterations start exceeding ~25 s in the
  log, the machine is paging again — check commit charge before anything else.

## Running the Phase 3 batch (written 2026-10-18, after the smoke test)

```
python -m src.phase3_runner --dry-run        # the plan, resume state, disk, environment
python -u -m src.phase3_runner --smoke       # two runs on video_01 into results/scratch/
python -u -m src.phase3_runner               # all 220 runs, arms in order
python -u -m src.phase3_runner --arms clean-subset
```

- **Launch detached** (section 1 above), then `watchdog_phase3.ps1`, also detached.
  Both are `ask`-gated in `.claude/settings.json`, so each needs explicit approval.
- **Watch a run in progress** with `tail -f results/ssrtd_real/runs/<run>/worker.log`.
  The runner's own log is `logs/phase3_runner.log`; failures land in
  `logs/phase3_errors.log` with the worker log tail attached.
- **Never two writers.** `results/ssrtd_real/runner.lock` holds the live pid; a second
  runner refuses to start. The watchdog also waits while a worker is still solving,
  so a killed runner cannot be replaced alongside its own child.
- **Resume is free.** Completed runs are skipped on the CSV key
  `(video_id, condition, factor, lam, seed)`; a run whose `summary.json` exists but
  whose row is missing is adopted, not recomputed.
- **It stops rather than crashing** below 2 GB free disk, and says how many runs are
  left. Budget ~2.2 MB per run plus 160-174 MB for each of the three figure videos.
- **Timing: 22-26 min per run**, depending on what else is using the CPU (the same
  smoke runs took 23.4 and 26.0 min). 220 runs is 80-95 h. Per-run timeout 3,600 s.
- **The manifest** `results/metrics/ssrtd_real_manifest.json` records the numerical
  environment of every runner start and appends rather than overwrites, so a numpy
  or OS change mid-batch stays visible (`RESEARCH_LOG.md` §6.6 for why).

### A space in the project path has now broken THREE launch commands

`E:\works\Video compression Research\...` contains a space, and every mechanism that
builds a command as a **string** has failed on it. Three instances, same root cause:

| when | what broke | symptom |
|---|---|---|
| 2026-09-17 | `Start-Process -ArgumentList` given an **array** with a spaced script path | the path was silently dropped and the watchdog never started (§1, "Two gotchas") |
| 2026-10-19 | `cmd /c ... >> logs\phase3_runner.log` redirected into the runner's **own** log | `PermissionError` within a second (above) |
| 2026-11-02 | `install_watchdog_task.ps1` passed a command **string** to `schtasks /create /tr` | `ERROR: Invalid argument/option - 'compression'.` -- PowerShell strips one layer of quoting, so the path split |

**Rule: never hand a spaced path to something that will re-parse it as a shell string.**
Prefer an API that takes the path as its own argument:

- Scheduled tasks: `Register-ScheduledTask` with `New-ScheduledTaskAction -Execute ...
  -Argument ...` objects, **not** `schtasks.exe`. The path is stored verbatim and no
  shell re-splits it. This is what the installer now does.
- `Start-Process`: pass `-ArgumentList` as ONE quoted string, and the directory via
  `-WorkingDirectory` rather than inside a `cd`.
- Python: `subprocess.run([...])` with a list, never `shell=True`.

**And test the quoting on this exact path**, not a short one. The 2026-11-02 fix was
verified by registering a real temporary task with the same action construction,
running it, and confirming `LastTaskResult: 0` plus the log line the script writes --
then removing the task.

### Committed but never run -- the gap this exposed

`install_watchdog_task.ps1` was committed on 2026-10-21 and first executed on
2026-11-02, when it failed immediately. The watchdog's **decision logic** had been
tested branch by branch; its **installer** had not been run once. Auditing the repo for
anything else in that position, 2026-11-02:

| code path | status |
|---|---|
| `install_watchdog_task.ps1` | **was** untested; now verified end-to-end (quoting, execution, exit code) |
| `--retry-failed` in `phase3_runner.py` | **was dead code** -- declared, documented, and never read in the body. Harmless only because resume keys on the CSV, so a failed run is already pending. Now documented as an accepted no-op rather than left looking like a safety net. |
| the **relaunch branch** of `watchdog_system.ps1` (its `Start-Process`) | still unexercised -- everything around it is tested, but the launch itself has never fired. It gets its first real exercise the first time the SYSTEM task relaunches the batch, and `logs/watchdog_system.log` plus a growing row count are the proof. Its `Start-Process` pattern is the one already proven by hand. |
| the `STOP_BATCH` branch of `watchdog_phase3.ps1` | unexercised -- added 2026-10-22; the sentinel has never existed while that watchdog was running. |
| the runner's disk-guard `STOPPING` branch | logic verified 2026-10-18 (§9.1) but never fired against a real full disk. |

The lesson is not "test more", it is **the untested line is the one that runs when
everything else has already gone wrong** -- an installer, a relaunch, a disk guard. Each
of those only executes in a failure, which is exactly when nobody is watching.

### The logoff-proof watchdog (2026-10-21)

`watchdog_phase3.ps1` is a user-session process and **dies in a logoff**, which is
what cost 18 idle hours on 2026-10-20 (`RESEARCH_LOG.md` §13). Use
`watchdog_system.ps1` via a SYSTEM Scheduled Task instead; keep the old one only for
watching a run in the foreground.

```powershell
# install (MUST be an elevated PowerShell -- a SYSTEM task needs admin)
powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Status
powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_watchdog_task.ps1" -Remove

# decide-and-log without launching anything (safe any time)
powershell -NoProfile -ExecutionPolicy Bypass -File ".\watchdog_system.ps1" -DryRun
```

- **Kill switch: create `STOP_BATCH` in the repo root.** While it exists the watchdog
  will not relaunch, and says so in `logs/watchdog_system.log`. Delete it to re-arm.
  It does **not** stop a runner that is already running -- kill the python process
  for that, then the sentinel keeps it stopped.
- **Stopping the batch deliberately is therefore two steps:** create `STOP_BATCH`,
  then kill the runner. In the other order the watchdog may relaunch it first.
- **Logs:** `logs/watchdog_system.log`. An unchanged state is logged once and then at
  most every 6 hours, so silence is normal; `logs/watchdog_state.json` holds the live
  state and the stall counter. Both the sentinel and the state file are gitignored on
  purpose -- a tracked kill switch could be restored by a `git checkout` and silently
  disarm the watch.
- **It gives up after 4 relaunches with no new rows** and tells you to delete
  `logs/watchdog_state.json` once the cause is fixed.
- **It does not defeat Modern Standby or a power-off.** For standby,
  `powercfg /change standby-timeout-ac 0`.

### Two things the real launch taught (2026-10-19)

- **Never redirect the detached launch into the runner's own log file.** The
  documented command in section 1 reads `>> logs\<runner>.log`; pointed at
  `logs\phase3_runner.log`, which `phase3_runner.py` also appends to itself, the
  runner dies **in under a second** with
  `PermissionError: [Errno 13] ... logs\phase3_runner.log`. Windows `cmd` opens a
  `>>` redirection target with exclusive sharing, so Python cannot also open it.
  The smoke test could not catch this: it was not launched through a redirection.
  Launch with a **separate** stdout file:

  ```
  python -u -m src.phase3_runner >> logs\phase3_runner.stdout.log 2>&1
  ```

  `watchdog_phase3.ps1` carried the same colliding redirection in its relaunch
  command, which would have been an **overnight silent failure**: relaunch, die in
  a second, no new rows, give up after four tries. Fixed; if the watchdog is ever
  re-derived from `watchdog_param_sweep.ps1`, check this line first.
- **This machine has 15.8 GB of RAM, not 7.8 GB** as section 3 above said (measured
  `Win32_OperatingSystem.TotalVisibleMemorySize` at launch, with 6.7 GB free and
  commit charge 80% while a dozen MCP server processes were running). The 2,663 MB
  per-run peak therefore has far more headroom than the notes assumed. The paging
  symptom to watch for is unchanged — iterations above ~25 s in the worker log.
- **A crashed start still leaves a manifest entry.** The 09:48:58 entry records the
  failed launch above; the 09:49:41 entry is the batch. That is the intended
  behaviour (the manifest records starts, and appends), not a duplicate to clean up.

## Not carried over

The other recovered notes were stale, and are deliberately **not** copied:

- **The June 2026 project overview is wrong on several points:** 58 videos (now 180), the
  dead `CCTV 01` path, `lam_s=0.001, lam_n=0.002`, the retracted "smoothness penalty
  removed (overflow)" claim, running compute on Colab, and a backup folder that does not
  exist.
- **The parameter-sweep result is already in git**, correctly labelled as the naive
  baseline, in `RESEARCH_LOG.md` §3.2 and `ARCHIVE_BASELINE.md`.
