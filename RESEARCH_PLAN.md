# RESEARCH PLAN — SS-RTD Surveillance Study (Pivot)

## Why we pivoted

The code previously called "SS-RTD" (`src/ssrtd.py`) does NOT implement SS-RTD. It has four
structural divergences from Shen et al. 2022 (see `RESEARCH_LOG.md` §4): no total-variation
smoothness term, no Tucker decomposition, two parameters instead of one λ, and a fixed
geometric penalty ramp instead of the adaptive conditional scheme. All prior results labeled
"SS-RTD" are mislabeled. A formal review scored the paper 4.5/10; the deepest issue is this
mislabeling.

## New paper framing (Path A+C merge)

**Research question:** does SS-RTD — designed and validated for SMOOTH X-ray foreground —
transfer to SHARP-EDGED surveillance foreground?

The old no-TV three-component method becomes an honest BASELINE (never called SS-RTD),
motivating why the TV smoothness term matters.

## What survives from prior work (reuse, do not rebuild)

- **VIRAT dataset** (180 videos, official Kitware, preprocessed)
- **Infrastructure:** `batch_runner.py`, `run_pipeline.py`, `compression.py` (H.264/ffmpeg),
  `metrics.py`, `param_sweep.py` harness — all method-agnostic
- **`tensor_rpca.py`** (correct two-component method) and its results
- **Paper scaffolding:** intro, methodology structure, experiments structure, citations,
  pipeline figure, LaTeX — NOTE: the manuscript is NOT in this repo. It lives in Overleaf
  (IEEE conference template). The `.tex` and `.bib` are there, not on local disk.

## What gets replaced

- `src/ssrtd.py` — replaced by a correct real-SS-RTD implementation

## The five phases

- **Phase 0 (DONE):** get paper, verify equations against rendered images, record truth.
  PDF on disk (gitignored, copyright), equations verified in `paper/SOURCE.md`, divergences
  in `RESEARCH_LOG.md`.
- **Phase 1:** implement real SS-RTD component-by-component, each unit-tested, then reproduce
  the paper's own results on a public benchmark (Candela/Caviar/Highway) BEFORE any VIRAT run.
  See `IMPLEMENTATION_PLAN.md` (to be written before Phase 1 coding begins).
- **Phase 2:** reframe research questions (two explicit questions; smooth-vs-sharp transfer).
- **Phase 3:** run real SS-RTD on 180 VIRAT via existing infrastructure; compression;
  parameter behavior across single λ; naive-baseline comparison.
- **Phase 4:** fix ALL reviewer points + the bugs the research log found (real PSNR/SSIM
  against proper reconstruction — the old 217 dB is meaningless; reframe L-vs-H.264 tautology;
  bound generalization; merge overlapping contributions; add variance/std; boundary tests;
  runtime; expand related work; Table II order; CRF ambiguity; `run_ssrtd` dead-code mismatch;
  add per-iteration logging so convergence/iteration cost is recoverable).
- **Phase 5:** rewrite paper around real results, in the author's own voice, section by section.

## Discipline (non-negotiable)

- Nothing is "done" until verified against the paper's equations (`paper/SOURCE.md`) or the
  paper's reported behavior.
- Plans and verified equations live on disk, readable by Claude Code — never only in
  conversation memory.
- When uncertain, check the PDF/`SOURCE.md` rather than guessing. Guessing caused the original
  mislabeling.
- Reproduce the paper's own results before trusting our implementation.
- Single λ ∈ [0.2, 1], never two parameters.
- Supervisor must approve scope before Phase 1 implementation proceeds.
