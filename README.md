# RPCA Surveillance Diagnostic

An empirical study of three-component tensor decomposition on surveillance video, using
the VIRAT Ground dataset.

## Correction to the earlier version of this repository

An earlier version of this repository and of the accompanying manuscript reported results
from `src/ssrtd.py` under the name **"SS-RTD"**, and said a smoothness penalty "from the
original paper" had been removed because it caused float64 overflow. **Both statements
were wrong.**

- `src/ssrtd.py` is **not** SS-RTD (Shen et al., IEEE TASE 2023). It is a **naive
  three-component baseline**. It differs from SS-RTD in four structural ways: averaged
  tensor SVT instead of Tucker/HOOI; no total-variation smoothness term; two L1 terms and
  two parameters instead of one; and an open-loop penalty ramp instead of an adaptive one.
- The code **never contained** a smoothness penalty, so none was removed, and no overflow
  was ever recorded. Git history shows this (`RESEARCH_LOG.md` §1; §4 items 1 and 5).

The results of that earlier version (the "component collapse" on 180 videos, the
lambda-ratio sweep, and the hybrid compression result) are properties of the **naive
baseline**. They are archived unchanged, with SHA256 checksums, in
`results/baseline_naive/`, which is kept locally and is not in this repository
(`ARCHIVE_BASELINE.md` describes the archive).

## What the study is now

SS-RTD has been **reimplemented from the paper** (`src/ssrtd_real.py`) and verified
against it: unit tests component by component, and a reproduction of the paper's own
Fig. 3 on its own data (`RESEARCH_LOG.md` §6).

The study asks what the **noise** component `E` of an `L + S + E` decomposition does
when the input contains no noise for it to represent. On clean VIRAT video, `E` claims
the support of the smooth-foreground component `S` far more often than chance on every
video. SS-RTD is the instrument used to measure this; the claim is about the model class.
Current state and results: `START_HERE.md`, `RESEARCH_LOG.md`.

## Methods

| Code | What it is | Name used |
|---|---|---|
| `src/ssrtd_real.py` | SS-RTD as published: Tucker/HOOI low-rank `L`, anisotropic-TV smooth `S`, L1 noise `E`, one `lambda`, adaptive ADMM penalties | "SS-RTD" |
| `src/ssrtd.py` | Naive three-component baseline: tensor SVT plus two soft-thresholded sparse terms `S`, `N`, parameters `lam_s`, `lam_n` | "the naive three-component baseline" (never "SS-RTD") |
| `src/tensor_rpca.py` | Two-component tensor RPCA | "Tensor RPCA" |

## Dataset

180 videos from **VIRAT Ground 2.0** (the `videos-01` subset), from the official Kitware
source. All source clips are 1280×720. Each is capped at 300 frames and processed at
**320×180 grayscale**, scaled to [0, 1]. `data/` is not in the repository.

## Repository structure

```
RPCA_Surveillance_Diagnostic/
├── src/
│   ├── ssrtd_real.py      # SS-RTD, reimplemented from the paper
│   ├── ssrtd.py           # naive three-component baseline (not SS-RTD)
│   ├── tensor_rpca.py     # two-component tensor RPCA
│   ├── gate_candela.py    # verification gate against the paper's Fig. 3
│   ├── phase3_*.py        # batch runner for the VIRAT runs
│   ├── test_*.py          # unit tests (plain scripts: python -m src.test_...)
│   ├── analysis/          # scripts behind the RESEARCH_LOG results
│   ├── preprocessing.py, metrics.py, compression.py, hybrid_encoder.py
│   └── run_pipeline.py, param_sweep.py, batch_runner.py   # baseline-era pipeline
├── paper/                    # source citation, manuscript audit, revision plan
├── RESEARCH_LOG.md           # the record: every decision, result and correction
└── START_HERE.md             # entry point
```

## Author

**IlmunIslam** — [github.com/IlmunIslam](https://github.com/IlmunIslam)
