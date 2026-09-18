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
- not sleep — sleep is disabled on AC power.

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
- **Revisit the 3600 s per-video timeout.** Measured 2026-09-19: **35.9 min per video**
  at 100 iterations (`RESEARCH_LOG.md` §7), before the H.264 step. That fits a
  60-minute limit, but individual iterations spiked to **48 s** while the machine
  paged, so the margin is thinner than the mean suggests. Budget the H.264 step
  before setting the timeout.
- **Memory is the other constraint — measured, not projected.** This machine has
  **7.8 GB** of RAM. The full-loop peak is **3,512 MB** per video after the `rfftn`
  change, yet the machine still paged around that peak: commit charge reached
  **93%** with ~1.1 GB headroom, and 15 iterations slowed to 25-48 s. Two allocation
  levers (the `tv_adjoint` temporary; `tv_forward(S)` computed three times per
  iteration) are being removed before the batch. Close other programs during the
  run regardless; even 250 MB processes matter at this margin.

## Not carried over

The other recovered notes were stale, and are deliberately **not** copied:

- **The June 2026 project overview is wrong on several points:** 58 videos (now 180), the
  dead `CCTV 01` path, `lam_s=0.001, lam_n=0.002`, the retracted "smoothness penalty
  removed (overflow)" claim, running compute on Colab, and a backup folder that does not
  exist.
- **The parameter-sweep result is already in git**, correctly labelled as the naive
  baseline, in `RESEARCH_LOG.md` §3.2 and `ARCHIVE_BASELINE.md`.
