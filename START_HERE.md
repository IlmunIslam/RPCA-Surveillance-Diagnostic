# START HERE — orientation for a fresh session

> Read this first, then the documents below in order. Everything needed to continue
> is in this repository; nothing depends on earlier chat history.
> Last updated 2026-09-17, at the end of Phase 1.

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
| 3 | `RESEARCH_LOG.md` | The authoritative record of what was actually done. §1 what the old code really was; §2 the reviewer's critique (4.5/10); §4 open problems; §5 deviations from the paper; **§6 the verification gate outcome**. |
| 4 | `PAPER_NOTES.md` | Every finding that must reach the manuscript, filed by section, each with its source. Item numbers are stable IDs, not reading order. |
| 5 | `ARCHIVE_BASELINE.md` | What the old method is, which of its results remain valid, which columns must never be quoted (the ~217 dB PSNR), and where its data is backed up. |
| 6 | `paper/SOURCE.md` | The source paper's citation plus its equations (3)-(14) and Algorithm 1, transcribed and checked against rendered page images. **This is the source of truth for the method.** |
| 7 | `PHASE3_NOTES.md` | Hard-won lessons for running long batches on this machine: the harness kills background jobs ~50 min in, so detach; smoke-test before a batch; resumability; memory. **Read before launching Phase 3.** |

## Where we are

**Phase 1 is complete.**

- **All seven components, (a) to (g1), are built and verified** in `src/ssrtd_real.py`:
  TV operators, Tucker/HOOI, the S/f/E updates, the multiplier and penalty updates, and
  the full Algorithm 1 loop. **162 assertions pass across seven test suites.**
- **(g2), the verification gate, PASSED for both E-threshold factors.** On the paper's own
  data (SBI Candela, 10% impulse noise, λ = 0.4), real SS-RTD reproduces the paper's
  Fig. 3. relErr_L at iteration 1 matched the paper to three decimals (0.0628 vs 0.0626).
  Details: `RESEARCH_LOG.md` §6.
- **Factor 1.0 is chosen for all VIRAT runs.** It fitted Fig. 3 better and matches the
  paper's Appendix A. ⚠️ The code default `E_THRESHOLD_FACTOR` is still **2.0**, so pass
  `factor=1.0` explicitly.

Run all seven test suites (from the repo root; the repo uses plain scripts, not pytest):

```
python -m src.test_tv_operators
python -m src.test_hooi
python -m src.test_s_update
python -m src.test_f_update
python -m src.test_e_update
python -m src.test_multipliers
python -m src.test_ssrtd_real
```

## The exact next step

**Phase 3: run real SS-RTD with `factor=1.0` on the 180 VIRAT videos.** The memory
work is done; the batch design is decided (`RESEARCH_LOG.md` §8: clean condition on
all 180 + noise-injected condition on the 20-video sweep subset); the next piece of
code is the batch runner (item 3 and `PHASE3_NOTES.md`).

**Handoff for the first session started at the repo root (written 2026-09-19).**
The previous session ran from the parent folder; `.claude/settings.json` was
committed in `9eaeeef` and applies only to sessions started here, after the trust
dialog is accepted. In this order, before anything else:

1. **Verify the deny rules fire, don't assume.** Attempt an Edit on
   `results/metrics/all_results.csv` and a Bash redirection (`echo x >>
   results/metrics/all_results.csv`); both must be refused. Show the refusals.
   Confirm `/status` lists *Project settings* under "Setting sources" (the user runs
   `/status` and `/permissions`; Claude cannot).
2. **Local settings files.** On Windows, `.claude/settings.local.json` is read from
   the start directory, so the parent folder's 60-rule file (`E:\works\Video
   compression Research\.claude\settings.local.json`, with `Bash(python *)` and
   `Bash(git push *)`) does **not** apply to repo-root sessions. The repo's own
   `.claude/settings.local.json` does; it still holds a stale `Bash(git push *)`
   allow (the committed `ask` rule wins regardless) and three `cd … &&` rules that
   are dead. Neither file is to be deleted unasked.
3. **Build the Phase 3 runner** per `RESEARCH_LOG.md` §8 "Runner requirements" and
   show the design before the first run; smoke-test one video; launch detached.

**Read `PHASE3_NOTES.md` before launching anything long.** Claude Code's
`run_in_background` has killed jobs about 50 minutes in on this machine, so the batch must
be launched detached (with a watchdog). The notes also cover smoke-testing, resumability
against the *new* results file, and the per-video timeout.

1. **Memory work — DONE 2026-09-19.** The `rfftn`/`irfftn` half-spectrum solve
   (`463de7e`) plus five allocation-only levers (`0be5c23` … `342e4d5`), each gated
   on **bitwise** reproduction of the pre-change solver (`test_ssrtd_real` test 7;
   248 assertions across seven suites). **Measured on one VIRAT video:** peak
   **3,512 → 2,663 MB**, **35.9 → ~22 min/video**, no paging — `RESEARCH_LOG.md`
   §7.1–§7.7. Batch projection ~66 h for 180 videos at 100 iterations, before H.264.
   float32 not needed; HOOI warm-start still off.
2. **The one-video measurement is done** (`results/scratch/measure_virat_one/`). It
   also gave a first look at the research question — `S` and `E` sharing sharp
   edges on clean video — recorded with caveats in `RESEARCH_LOG.md` §7.4 and
   `PAPER_NOTES.md` item 18. The noise-injected condition question is settled:
   `RESEARCH_LOG.md` §8.
3. **Follow the output contract** (`IMPLEMENTATION_PLAN.md`): write to new filenames
   (never `all_results.csv` / `param_sweep.csv`), add an explicit `method` column, and log
   every iteration. The old results are frozen in `results/baseline_naive/`.

After that: **Phase 2** (reframe the research questions: does smooth-foreground SS-RTD
transfer to sharp surveillance foreground?), then **Phase 4** (fix the reviewer points)
and **Phase 5** (rewrite the paper around the real results, in the author's own voice).

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
