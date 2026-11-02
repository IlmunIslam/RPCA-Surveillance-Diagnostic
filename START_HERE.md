# START HERE — orientation for a fresh session

> Read this first, then the documents below in order. Everything needed to continue
> is in this repository; nothing depends on earlier chat history.
> Last updated 2026-11-02, mid-Phase 3: three arms complete, `clean-rest` at 54/160.

## What this project is

This repository is a faithful reimplementation of **SS-RTD** (Shen et al., IEEE TASE
2022), used to test whether a method designed for smooth X-ray foreground transfers to
sharp-edged surveillance video (VIRAT), for an IEEE Access paper that received a major
revision. The project pivoted after we discovered that the old code (`src/ssrtd.py`),
whose results the original manuscript reported as "SS-RTD", **was not SS-RTD**: it had no
total-variation term, no Tucker decomposition, two parameters instead of one, and a
different penalty schedule. That old method is now kept as an honestly labelled **naive
baseline**, and the real SS-RTD has been rebuilt from the paper and verified against the
paper's own results.

## Read these, in this order

| # | Document | What it contains |
|---|---|---|
| 1 | `RESEARCH_PLAN.md` | Why we pivoted, the new paper framing, the five phases, the figures plan, and the working discipline. *Its phase list predates Phase 1's completion — trust this file and #2 for current status.* |
| 2 | `IMPLEMENTATION_PLAN.md` | The Phase 1 build spec, component by component (a)-(g2), each with its verified status and measurements; the **output contract** Phase 3 must follow; the carry-forward decisions under (g). |
| 3 | `RESEARCH_LOG.md` | The authoritative record of what was actually done. §1 what the old code really was; §2 the reviewer's critique (4.5/10); §4 open problems; §5 deviations from the paper; **§6 the verification gate outcome**; **§8 the batch design**; **§10, §12, §14 the three completed arms and their results**; §11 the λ-sweep decision; §13 the batch-reliability incidents; **§15 clean-rest, PROVISIONAL at 54/160**. |
| 4 | `PAPER_NOTES.md` | Every finding that must reach the manuscript, filed by section, each with its source. Item numbers are stable IDs, not reading order. |
| 5 | `ARCHIVE_BASELINE.md` | What the old method is, which of its results remain valid, which columns must never be quoted (the ~217 dB PSNR), and where its data is backed up. |
| 6 | `paper/SOURCE.md` | The source paper's citation plus its equations (3)-(14) and Algorithm 1, transcribed and checked against rendered page images. **This is the source of truth for the method.** |
| 7 | `PHASE3_NOTES.md` | Hard-won lessons for running long batches on this machine: the harness kills background jobs ~50 min in, so detach; smoke-test before a batch; resumability; memory. **Read before launching Phase 3.** |

## Where we are

**Phase 1 is complete and Phase 3 is running.** 114 of 300 batch runs are done.

**Phase 1.** All seven components (a)-(g1) are built and verified in
`src/ssrtd_real.py`; **248 assertions pass across seven test suites**. The (g2)
verification gate PASSED for both E-threshold factors on the paper's own data (SBI
Candela, 10% impulse, λ = 0.4), reproducing Fig. 3 with relErr_L at iteration 1 of
0.0628 against the paper's 0.0626 (`RESEARCH_LOG.md` §6). **Factor 1.0 is chosen for
all VIRAT runs** — it fits Fig. 3 better and matches Appendix A. ⚠️ The code default
`E_THRESHOLD_FACTOR` is still **2.0**, so pass `factor=1.0` explicitly. Memory work is
done: peak **2,663 MB**, ~22-26 min per video, every change verified **bitwise**
(§7.1-§7.7).

### Phase 3 batch: 114 / 300 runs

| arm | runs | status | where |
|---|---|---|---|
| `clean-subset` | 20 / 20 | ✅ complete | §10 |
| `noise-subset` | 20 / 20 | ✅ complete | §12 |
| `factor2-subset` | 20 / 20 | ✅ complete | §14 |
| `clean-rest` | **54 / 160** | running, interrupted | §15 (**PROVISIONAL**) |
| `lambda-sweep` | 0 / 80 | queued, runs last | §11 |

**Zero failed runs in 114.** The eight FAILED entries in `logs/phase3_errors.log` are
all from the 2026-10-20 logoff (§13) and computed nothing.

### The headline result so far

`S` and `E` do not separate: `E`, the designated **noise** term, lands on the same
sharp background edges `S` claims. Measured as **enrichment over independence**,
`P(E-claimed | S-claimed) / P(E-claimed)`, which is 1.0 if the supports are
independent:

- **74 / 74 clean videos above 1**, pooled median **39.7x** (§10, §15).
- **Dose-response:** the effect is *stronger the emptier the scene* — Spearman
  **−0.613** against `foreground_density` over 74 videos, and it survives the
  support-size confound (§10.3).
- **Corroborated under noise:** measured on uncorrupted voxels, the noise arm gives
  median 41.9x against the clean arm's 40.4x, rank correlation **+0.994** between arms
  (§12.1). So the sink is not an absence-of-noise artifact.
- **Robust to the printed threshold:** at the `factor = 2.0` of eq. (12) the effect
  halves but stays above 1 on 20/20, with video ordering preserved (ρ = +0.847, §14).
- ⚠️ **Never quote the raw overlap share alone**, and never the pooled-over-videos
  ratio: on the subset `video_01` alone carries 90% of the expected count (§10.1).
  Quote the median per-video enrichment with its range.
- ⚠️ **`video_01` is the WEAKEST of the 20** (2.4x) because its scene is far busier
  than typical. Every figure and early number came from it, so it *understates* the
  effect (§10.2).

**Framing** (`PAPER_NOTES.md`, framing section): the contribution is **not** "SS-RTD
does not transfer". It is that a three-component model's designated noise term becomes
a **misfit sink** when that noise is absent, and the sink coincides with the sparse
term more completely the emptier the scene. **SS-RTD is the instrument, not the
subject.** Five places in the record still state the narrower "does it transfer"
framing; they are listed in that section, flagged and not yet rewritten.

## The exact next step

**Relaunch the batch: 186 runs pending** (106 of `clean-rest`, then the 80-run λ
sweep). ~81 h of compute if the machine does not page.

```
python -m src.phase3_runner --dry-run     # plan, resume state, disk, environment
python -m src.phase3_checkpoint --arm clean-rest
```
Launch detached, per `PHASE3_NOTES.md` §1 — **never** redirect into
`logs/phase3_runner.log`, which the runner writes itself:
```powershell
Start-Process -FilePath cmd.exe -ArgumentList '/c','python -u -m src.phase3_runner >> logs\phase3_runner.stdout.log 2>&1' -WorkingDirectory "E:\works\Video compression Research\RPCA_Surveillance_Diagnostic" -WindowStyle Hidden
```
Resume is free and keyed on the CSV; `summary.json` is written **last** as the
completion marker, so an interrupted run is simply recomputed. This has now been
confirmed under three real kills (§13.1).

### Batch reliability — read before relaunching

The batch has been interrupted **three times**, and each time the loss was the
*undetected idle*, not the crash:

| when | cause | idle |
|---|---|---|
| 2026-10-20 00:27 | **Modern Standby** suspended a run 92 min (Kernel-Power 506/507). The per-run timeout cannot catch it: parent and child are suspended together, so it bounds *active* time only. §12 | — |
| 2026-10-20 10:38 | **Logoff** killed worker, runner and watchdog together (`0xC000026B`). §13 | 18 h |
| 2026-10-23 11:31 | **Clean OS restart** (EventLog 6006, Kernel-Power 109, boot 6005 at 11:37). The foreground watchdog had correctly relaunched a dead runner at 11:19, then died in the restart. | **10.5 days** |

- **`watchdog_system.ps1` + a SYSTEM Scheduled Task is the fix** and survives logoff
  and reboot: `install_watchdog_task.ps1`, **from an elevated shell**. Verify with
  `schtasks /query /tn Phase3BatchWatchdog` — "cannot find the file specified" means it
  is **not** installed. As of 2026-11-02 it had not been.
- **Kill switch: create `STOP_BATCH` in the repo root.** Both watchdogs honour it.
  Stopping the batch deliberately is two steps: create `STOP_BATCH`, *then* kill the
  runner. Gitignored on purpose, so a checkout cannot resurrect it.
- **Modern Standby needs `powercfg /change standby-timeout-ac 0`** — nothing in the
  repo can prevent it.
- **Memory is the live constraint.** Worker peak **2.8 GB** of 15.8 GB total; when
  available memory drops near that, iterations go from ~15 s to 40-60 s and a run can
  approach the 3,600 s timeout (`video_01` at factor 2.0 took 57.4 min). Many
  uniformly slow iterations = paging; one enormous iteration = standby.


## What the paper still has to fix

**The four remaining reviewer-critical problems** (`RESEARCH_LOG.md` §2). The reviewer's
first problem — reporting a modified method under the name "SS-RTD" — is what the pivot
itself fixes.

1. **PSNR/SSIM promised but never reported** — and the old values (~217 dB) were
   tautological. Report real PSNR/SSIM against a proper reconstruction.
2. **The L-vs-H.264 compression comparison is unfair**: it compares a static background
   against full video with motion. Reframe it, or use a quality-matched comparison.
3. **The two headline contributions overlap**: the 180-video collapse and the 20-video
   parameter sweep show the same mechanism at different scales. Merge them.
4. **The generalization goes too far**: one method, one dataset, reduced resolution and
   short clips. Narrow the claims to what was tested.

Minor points (Table II row order, related work, runtime, CRF ambiguity, sensitivity) are
listed in `RESEARCH_LOG.md` §2 and `RESEARCH_PLAN.md` Phase 4.

**Documented rigor findings about the source paper**, each verified and each needing a
disclosure in the manuscript (full detail in `PAPER_NOTES.md`):

| Item | Finding |
|---|---|
| 1 | The rank rule (0.8H, 0.8W, 1) is infeasible for non-square frames — r3 = 1 forces r1 = r2 |
| 11 | eq. (12) prints threshold 2/β^X, but Appendix A's derivation implies 1/β^X — the gate data favours 1/β^X |
| 14 | Algorithm 1's stopping rule halts after one iteration if taken literally |
| 15 | The printed PSNR formula omits the division by pixel count; the reported numbers fit the standard one |
| 17 | *Candidate, inference only:* the paper's SSIM (0.9019) likely used MATLAB's default dynamic range of 1 on 0-255 images |

Also disclosed where the paper is silent or ambiguous: item 2 (L's frames are
proportional, not identical), item 10 (anisotropic vs isotropic TV), item 12 (β^X's
error measure is our inference). One open, unexplained observation: relChg_L runs about
5x the paper's value in iterations 15-40 (`RESEARCH_LOG.md` §6.3).

## Discipline (non-negotiable)

- **Nothing is "done" until it is verified** against `paper/SOURCE.md` or the paper's
  reported results. Guessing is what caused the original mislabelling.
- **Plans and findings live on disk, not in chat memory.** If it matters, it goes into
  one of the documents above and gets committed.
- **When unsure, check the PDF** (repo root, gitignored for copyright) — render the page
  and read it rather than trusting text extraction, which garbles equations.
- **Build in small verified steps:** spec first, then code, then tests that pass, then
  commit. Tests must be able to catch the realistic failure, not just confirm the formula.

## Working conventions

- **Commits:** authored `Ilmun Islam <ilmunislam101@gmail.com>` (pinned in the repo's
  local git config). **No `Co-Authored-By` or `Claude-Session` trailers.**
- The user reviews specs before code and results before commits, and supplies commit
  messages. Don't commit or run long jobs without being asked.
- Paths are relative to `PROJECT_DIR = Path(__file__).parent.parent`; never hardcode
  absolute paths.

## Only on local disk (not on GitHub)

`data/` (VIRAT videos, SBI Candela frames and ground truth), `results/` (the old baseline
CSVs — also backed up to OneDrive `RPCA-Baseline-Archive-2026-09-09\` — plus
`results/gate_candela/`), `logs/`, and the source-paper PDF. All are gitignored.
`results/gate_candela/` can be regenerated with `python -m src.gate_candela --factor both`
(~30 min).
