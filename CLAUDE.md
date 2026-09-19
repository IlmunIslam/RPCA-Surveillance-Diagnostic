# RPCA Surveillance Diagnostic Research

> **Read `START_HERE.md` first.** It is the entry point and carries the full current
> state: what is built, what is verified, the exact next step, and the reading order for
> the other documents. This file is only a short orientation that loads automatically.

## What this project is

A **faithful reimplementation of SS-RTD** (Shen et al., IEEE TASE 2022,
DOI 10.1109/TASE.2022.3163674), used to ask whether a method designed and validated on
smooth X-ray foreground transfers to sharp-edged surveillance foreground (VIRAT), plus a
comparison against a **naive three-component baseline**. Target: IEEE Access (a major
revision of an earlier submission).

The project pivoted in 2026-09 after discovering that the code the original manuscript
called "SS-RTD" is not SS-RTD. See `RESEARCH_LOG.md` §4 item 1.

## Two methods, two names — never mix them

| Code | What it is | How to refer to it |
|---|---|---|
| `src/ssrtd_real.py` | **Real SS-RTD**: Tucker/HOOI for `L`, anisotropic TV for `S`, L1 for noise `E`, a single `lambda`, adaptive ADMM penalties. Verified against the paper. | "SS-RTD" |
| `src/ssrtd.py` | The **naive three-component baseline**: tensor SVT plus two independent soft-thresholded components. No TV term, no Tucker, two parameters. | "the naive three-component baseline" — **never** "SS-RTD" |
| `src/tensor_rpca.py` | Correct two-component Tensor RPCA. Untouched by the pivot. | "Tensor RPCA" |

## Never repeat these

- **There was never a smoothness penalty in `src/ssrtd.py`, so it was never removed and
  never overflowed.** Git forensics proved it (`RESEARCH_LOG.md` §1). The old
  "smoothness penalty REMOVED (caused overflow)" claim is retracted — do not restate it.
- **Never quote `ssrtd_psnr`, `ssrtd_ssim`, `tensor_psnr` or `tensor_ssim`** from
  `all_results.csv` (~217 dB). They measure the ADMM constraint residual, not quality.
  See `ARCHIVE_BASELINE.md` §3.
- **`lam_s=0.01, lam_n=0.001` is the baseline's setting, not "the method's".** Real
  SS-RTD has exactly one parameter, `lambda`, in [0.2, 1].

## Dataset

180 VIRAT Ground 2.0 videos (videos-01 subset), at `data/videos/` relative to the repo
root; `video_registry.csv` maps short IDs. First 300 frames per video, grayscale,
downsampled to 320x180. Annotations in `data/annotations/`. `data/` is gitignored.

## Key technical decisions (current)

- **Real SS-RTD:** single `lambda` in [0.2, 1]. **Pass `factor=1.0` explicitly** — the
  code default `E_THRESHOLD_FACTOR` is 2.0, the paper's printed value, but the
  verification gate chose 1.0 (`RESEARCH_LOG.md` §6.1).
- Tucker ranks are clamped to what is attainable: `(144,144,1)`, not the paper's
  `(144,256,1)` (`RESEARCH_LOG.md` §5 item 1).
- Compression measured with H.264 via ffmpeg, CRF 23 reference and CRF 28 components.
- **Output contract** (binding on Phase 3): new runs write
  `results/metrics/ssrtd_real_results.csv`, carry an explicit `method` column, do not
  reuse the `ssrtd_*` column prefix, and log per-iteration state. Never write into
  `all_results.csv` or `param_sweep.csv` — the baseline results are frozen in
  `results/baseline_naive/`. Details in `IMPLEMENTATION_PLAN.md`.

## Running things

All compute runs locally. Tests are plain scripts, not pytest:

```
python -m src.test_tv_operators   python -m src.test_hooi        python -m src.test_s_update
python -m src.test_f_update       python -m src.test_e_update    python -m src.test_multipliers
python -m src.test_ssrtd_real
```

**Before launching anything long, read `PHASE3_NOTES.md`.** Background jobs have been
killed about 50 minutes in on this machine, so long runs must be launched detached.

## Conventions

- Commits authored `Ilmun Islam <ilmunislam101@gmail.com>`; **no `Co-Authored-By` or
  `Claude-Session` trailers**.
- The user reviews specs before code and results before commits, and supplies commit
  messages. Don't commit or launch long jobs unasked.
- Paths derive from `PROJECT_DIR = Path(__file__).parent.parent`; never hardcode absolute
  paths.
- Nothing is "done" until verified against `paper/SOURCE.md` or the paper's own results.

## Current status

Phase 1 complete: real SS-RTD built and unit-tested (248 assertions, seven suites), and
the Candela verification gate passed, reproducing the paper's Fig. 3. The memory work
is done (peak 2,663 MB, ~22 min per video, every change verified bitwise). Next is
Phase 3 — the batch runner for the 180-video VIRAT run with `factor=1.0`. See
`START_HERE.md`.
