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

- **Launch detached** (section 1 above). **The SYSTEM Scheduled Task is the only
  watchdog**; nothing else needs starting -- see "The only watchdog" below.
- **Watch a run in progress** with `tail -f results/ssrtd_real/runs/<run>/worker.log`.
  ⚠️ Safe for that file (Python writes it) but **never `tail -f`
  `logs/watchdog_system.log`**: MSYS `tail` holds it in a share mode that silently
  blocks PowerShell's `Add-Content`, so the watchdog's own lines vanish while it
  keeps working (`RESEARCH_LOG.md` §18). Read it with `Get-Content -Tail` instead.
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

### Monitoring a long batch leaks `tail` processes

Watching `logs/phase3_runner.log` with a 30-minute `tail -f` watcher, re-armed each
time it expired, left **one orphaned `tail` per cycle: 40 had accumulated by
2026-11-03** before they were noticed and killed. **A stopped monitor can orphan its
`tail`** -- stopping the watcher ends its shell but not necessarily the `tail` it
spawned, so check for strays and kill them rather than assuming the stop cleaned up:

```powershell
Get-Process tail -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
```

This is not cosmetic. It is the **same leak** that silently blocked the watchdog's
`Add-Content` writes on 2026-11-03: an orphaned `tail` holds a Windows file in a share
mode that blocks PowerShell appends, so two real watchdog firings wrote state but no
log line (`RESEARCH_LOG.md` §18). A future session re-running the same
watch-and-re-arm loop would rebuild the leak, so prefer **periodic spot-checks of the
row count** over a continuous tail for a multi-day batch, and never tail a log that
PowerShell writes.

### Checks that report confidently while structurally blind

Four instances in this project, in different clothes each time. The common shape:
**the check's failure mode is indistinguishable from a reassuring answer**, so it
reports success it never established.

| # | the check | what it claimed | why it was blind |
|---|---|---|---|
| 1 | the `Edit(...)` deny rules on the frozen CSVs | documented as guarding them | the session was keyed to the parent folder, so `.claude/settings.json` was never read. A redirection appended to `all_results.csv` on the first real test (ARCHIVE_BASELINE §7) |
| 2 | `watchdog_system.ps1`'s relaunch | logged "relaunching" | it never checked whether the process started. `python` was not on SYSTEM's PATH, so it logged two successes while achieving nothing (RESEARCH_LOG §16.1) |
| 3 | "the task does not exist -- verified two ways across 412 tasks" | absence of the Scheduled Task | `C:\Windows\System32\Tasks\` is Access-denied to a standard user, and `Win32_Process.CommandLine` is unreadable for session-0 processes. Enumeration from an unelevated session cannot prove absence (RESEARCH_LOG §17.1) |
| 4 | `dirty = bool(_git("status", "--porcelain"))` | a clean working tree | a clean tree returns `""` **and so does a git that never ran**. With git absent under SYSTEM the manifest asserted `dirty: false` on a tree nobody checked (RESEARCH_LOG §17.2) |

**Two rules, both earned:**

1. **Every check must be able to say "unknown".** `_git()` now returns `None` on
   failure and `environment()` records `"unknown"` for `commit`, `commit_short`,
   `dirty` and `untracked_paths`, with the runner logging "provenance is lost, not
   clean". A tri-state is the fix; a boolean that collapses failure into the happy
   value is the bug.
2. **Verify by observing the thing claimed, not by the absence of a complaint.** A
   guardrail is proven by a blocked write, a watchdog by a pid and a new row, a
   Scheduled Task by a log line it wrote -- never by a query that could be blind to
   what it is looking for.

A fifth near-instance, worth remembering because it was self-inflicted: watching
`logs/watchdog_system.log` with `tail -f` **silently blocked** PowerShell's
`Add-Content` to it, so two real watchdog firings wrote state but no log line. The
orphaned `tail` handles survived stopping the monitor. **Observing a Windows log file
can suppress writes to it** -- when a log goes quiet, check for readers holding it
before concluding the writer stopped.

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
| the **relaunch branch** of `watchdog_system.ps1` (its `Start-Process`) | **FAILED on first execution, 2026-11-03** -- bare `python` is not on SYSTEM's PATH, and it logged a success it had not achieved (RESEARCH_LOG §16). Fixed and re-verified under the user account (runner pid 2452). Still **not** proven under SYSTEM: that needs the task re-registered and a kill test. |
| the `STOP_BATCH` branch of `watchdog_phase3.ps1` | ✅ **verified 2026-11-03**: with the sentinel present it logged "STOP_BATCH present - not relaunching" and did not relaunch; on removal, "STOP_BATCH removed - watching again" at the next poll. Each logged once, and the live runner was untouched. |
| the runner's disk-guard `STOPPING` branch | still unexercised, and **not cheaply testable**: it needs either ~15 GB of real disk consumed or an injectable threshold. A second runner cannot reach the guard while a batch is live, because `acquire_lock()` refuses first. The fix, when convenient, is a `--min-free-gb` override so the branch can be fired on demand; until then this is a known-untested path. |

The lesson is not "test more", it is **the untested line is the one that runs when
everything else has already gone wrong** -- an installer, a relaunch, a disk guard. Each
of those only executes in a failure, which is exactly when nobody is watching.

### PENDING at the clean-rest boundary (author's instruction, 2026-11-04)

`clean-rest` will land at **159 / 160**, not 160: `video_87` timed out on 2026-11-03
(§13-style memory pressure, `RESEARCH_LOG.md` §17 era) and the runner had already
moved past it in this pass's plan, so it is still pending and this pass will not
retry it.

**Do ONE restart at the boundary** -- kill the runner (SYSTEM-owned, needs an elevated
shell) and let the SYSTEM task relaunch it. Resume re-queues `video_87` automatically;
`--retry-failed` is the documented no-op. Then the arm analysis is on the full 160.

**Then report the full-arm result** and compare against the subset (median enrichment
**40.4x**, range **2.4-199.8x**) and against the PROVISIONAL §15 figures at n=54
(median **38.1x**, rho **-0.606**): median and range, the density dose-response, and
whether §15 holds at n=160. **If it diverges, say so plainly and supersede §15**
rather than quietly editing it -- the same discipline as the withdrawn precision claim
of §12.2.

### The only watchdog (retired the second one, 2026-11-03)

**`watchdog_system.ps1`, run by the SYSTEM Scheduled Task `Phase3BatchWatchdog`, is
the ONLY watchdog.** `watchdog_phase3.ps1` is **retired and deleted**; it stays in
git history if ever wanted (`git show 6c2fd18:watchdog_phase3.ps1`).

Why retired rather than maintained: it was a user-session process and **died in a
logoff**, which is what cost 18 idle hours on 2026-10-20 and 10.5 days on 2026-10-23
(`RESEARCH_LOG.md` §13, §17). The SYSTEM task does everything it did and survives
logoff and reboot; its only advantage was a 60-second poll against 15 minutes, which
is irrelevant for a multi-day unattended batch. The decisive argument: **two
watchdogs is how the bare-python bug survived in one file after being fixed in the
other** -- it sat in `watchdog_phase3.ps1:104` for days after `watchdog_system.ps1`
was repaired, working only because a human always started it (author's decision,
2026-11-03). `watchdog_param_sweep.ps1` stays untouched: baseline-era and unused.

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

## Enrichment's denominator does the work (the quantitative sibling of the rule above)

> **Whenever enrichment is compared between two populations whose `E`-density differs,
> the denominator does the work. Report the raw conditional `P(E|S)` alongside, every
> time.**

`enrichment = P(E | S-claimed) / P(E)`. The second factor is a property of the
*population*, not of any relationship between `S` and `E`, so comparing enrichment
across populations that differ in how often `E` fires measures mostly that difference.

Five instances in this project:

| where | populations compared | caught? |
|---|---|---|
| `RESEARCH_LOG.md` §14 | `factor` 1.0 vs 2.0 | yes |
| §20.7b | measurement threshold 0.01 vs 0.05 | yes -- the 47.4x headline is threshold-specific |
| §21.2 | clean vs noise (`beta_X` differs 1.53x) | **yes, before the test** -- which is the only reason §22 is interpretable |
| §22.3 | an unexplained 3-8% clean/noise excess | yes, and left unclaimed |
| **§25.4** | inside vs outside annotation boxes (`E` 17.60x denser inside) | **NO** -- reported to the author as a strong result first, then withdrawn |

§25.4 is the one that got through. The gap looked like a 14.71x effect at p 2.6e-26 on
157 of 179 videos; the raw conditional was 31.5% inside against 29.8% outside, i.e.
flat. The check took four minutes and the alternative was a confound as the
manuscript's headline mechanism result.

This sits beside the older rule -- *every check must be able to say "unknown"* -- and
has the same shape: **a statistic that reports confidently while being structurally
unable to distinguish the effect from a nuisance parameter.**
