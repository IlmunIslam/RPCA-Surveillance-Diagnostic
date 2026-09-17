# ARCHIVE — the baseline method and its results

> Written 2026-09-09, before real SS-RTD implementation begins (Phase 1).
> Purpose: preserve the pre-pivot work so nothing is lost, and so old and new
> results can never be confused. See `RESEARCH_PLAN.md` for the pivot,
> `RESEARCH_LOG.md` §4 item 1 for why the relabeling was necessary.

## 1. What the old method actually is

Three-component tensor decomposition `X = L + S + N`, where:

- `L` is low-rank, obtained via **tensor SVT** — SVD soft-threshold applied to all
  three mode-unfoldings, refolded and averaged (`src/ssrtd.py:29-39`).
- `S` and `N` are two **independent sparse components**, each produced by plain
  soft-thresholding with its own weight, `lam_s` and `lam_n`
  (`src/ssrtd.py:87-88`).
- **No smoothness / total-variation term. No Tucker decomposition.**

It is essentially **"Tensor RPCA with the sparse part split into two
soft-thresholded components."** Implemented in `src/ssrtd.py`.

**This is not SS-RTD and not a variant of it.** Real SS-RTD (Shen et al. 2022,
see `paper/SOURCE.md`) uses Tucker/HOOI for `L`, an anisotropic-TV penalty on `S`,
a single tuning parameter `lambda`, and an adaptive conditional penalty schedule.
None of those four elements is present here. The module filename, the
`ssrtd_*` CSV columns, and the docstring all still carry the old name — they are
historical labels, not claims.

The docstring in `src/ssrtd.py` additionally claims a smoothness penalty was
removed because it "causes float64 overflow." **That never happened.** Git
history shows no such penalty was ever present in this repository
(`RESEARCH_LOG.md` §1). Do not repeat that claim anywhere.

## 2. Its role going forward

This becomes the **BASELINE** in the new paper: the naive three-component
decomposition that motivates why real SS-RTD's TV smoothness term matters.

It gets a real name of its own during Phase 2 — it needs one, since it does not
exist in the literature under any name. Until then, refer to it as "the naive
three-component baseline", never as SS-RTD.

## 3. What results it produced (all VALID as baseline data, just relabeled)

### `results/metrics/all_results.csv` — 180 rows, 28 columns

- Three-component decomposition over all 180 VIRAT videos at
  `lam_s=0.01, lam_n=0.001`: winner = `N` in **180/180**, i.e. the
  parameter-controlled collapse.
- Tensor RPCA (`L + S`) results for the same 180 videos.
- Hybrid (`L_tensor + N_ssrtd`) results, including H.264 sizes.

### `results/metrics/param_sweep.csv` — 100 rows

20 videos x 5 configurations, establishing that the winner is decided by the
`lam_s`/`lam_n` **ratio** alone, unanimously (20/20 in every configuration),
independent of scene content or foreground density.

### CAVEAT — which columns are trustworthy

**NOT valid as quality metrics:** `ssrtd_psnr`, `ssrtd_ssim`, `tensor_psnr`,
`tensor_ssim`. These compare the original frames against `L + S + N` (or
`L + S`), which *is* the ADMM constraint — so they measure the converged
constraint residual, not reconstruction quality. That is why the values are
physically impossible as quality scores: median `ssrtd_psnr` **217.4 dB**,
`tensor_psnr` **205.5 dB**, SSIM pinned at 1.0. Regenerate real quality metrics
in Phase 4. Never quote these numbers.

**Valid:** the sparsity and winner columns (`ssrtd_s_sparsity`,
`ssrtd_n_sparsity`, `ssrtd_s_nonzero_pct`, `ssrtd_n_nonzero_pct`,
`ssrtd_winner`, `tensor_s_sparsity`), the size columns (`original_ref_kb`,
`original_comp_kb`, `L_tensor_kb`, `S_tensor_kb`, `N_ssrtd_kb`, `hybrid_kb`),
`foreground_density`, the timing columns, and `hybrid_psnr` (median **30.70 dB**)
together with the `*_after_h264` columns — those measure something genuinely
lossy.

**Unverified:** `hybrid_compression_ratio` (median 0.4773). A median below 1
reads as "smaller than reference", which contradicts the raw KB columns and the
reported finding. `src/compression.py` has not been audited. Do not quote this
column until it is. See `RESEARCH_LOG.md` §4 item 8.

## 4. What survives fully and correctly

- **Tensor RPCA** (`src/tensor_rpca.py`) — a correct two-component method,
  correctly labeled, with valid results. Nothing about the pivot touches it.
- **The hybrid negative result** — the hybrid never beats H.264: 0/180 videos,
  1.35x to 1.87x larger than baseline, mean 1.55x. Confirmed consistent across
  the CSV, the code and the manuscript.
- **The parameter-sweep mechanism finding** — two interchangeable L1 penalties
  competing for one residual produce winner-takes-all decided by the weight
  ratio. This is a real property of the baseline method and remains a valid
  finding about *it*. It is not a finding about SS-RTD.

## 5. Backup status of the result CSVs — ✅ DONE 2026-09-09

The two baseline CSVs are now backed up in three places, **verified byte-identical
by SHA256 (re-checked 2026-09-18)**:

| Copy | Location | Protects against |
|---|---|---|
| Original | `results/metrics/` | — |
| Frozen snapshot | `results/baseline_naive/` (with a README) | overwrite, confusion with new runs |
| Off-disk | `C:\Users\ilmun\OneDrive\RPCA-Baseline-Archive-2026-09-09\` (with a README) | disk failure |

| File | Size | Rows | Last modified |
|---|---|---|---|
| `all_results.csv` | 33,623 B | 180 | 2026-06-28 09:42 |
| `param_sweep.csv` | 10,311 B | 100 | 2026-07-04 03:07 |

**Why this was urgent (state before 2026-09-09):** both files existed on this disk
only. They are ignored by `.gitignore:5` (`results/`), so they are in no commit and
not on GitHub; a search of the whole `E:\works\Video compression Research` tree
found no other copy; and OneDrive is rooted at `C:\Users\ilmun\OneDrive`, outside
the `E:` drive. A disk failure or a bad run would have cost the 180-video batch,
which ran 2026-06-22 to 2026-06-28.

⚠️ **Still not backed up: `results/figures/` (2.0 GB)** — also gitignored, still on
this disk only. Regenerable from the CSVs and the videos, so lower value than the
CSVs, but it is not protected.

### The overwrite risk is real, and it is contamination rather than deletion

Both writers **append**:

- `src/run_pipeline.py:206-209` reads the existing `all_results.csv`, concatenates
  the new row and rewrites the file. There is **no dedupe on `video_id`**, so a
  re-run adds a second row for the same video rather than replacing it.
- `src/param_sweep.py:110-111` appends to `param_sweep.csv` when it already exists.

Combined with the fact that new real-SS-RTD runs would write into the **same
`ssrtd_*` column names**, this means a Phase 3 run against the existing files
would interleave old baseline rows and new SS-RTD rows with **nothing in the data
to tell them apart**. That is precisely the confusion this archive exists to
prevent, and it would be silent.

## 6. Terminology mapping for the archived columns (the files are NOT renamed)

**Decision 2026-09-18: the archived CSVs stay exactly as they are.** All three
copies of each file are verified byte-identical by SHA256 (§5). Renaming columns
in place would invalidate that verification and require redoing every copy, and
rewriting archived result files to match later terminology is the kind of edit
that reads as tampering. So the stored data is immutable, and the current
terminology is applied in the **analysis and figure scripts that read these
files**, never in the files themselves.

Every `ssrtd_*` name below refers to the **naive three-component baseline**
(`src/ssrtd.py`), not to SS-RTD. Read the columns as follows:

**`all_results.csv`**

| Archived column | What it actually is | Current term |
|---|---|---|
| `tensor_*` | Tensor RPCA, `L + S` — correct method, correctly named | Tensor RPCA |
| `ssrtd_psnr`, `ssrtd_ssim`, `tensor_psnr`, `tensor_ssim` | ADMM constraint residual, not quality (§3) | **do not quote** |
| `ssrtd_s_sparsity`, `ssrtd_s_nonzero_pct` | the baseline's `S`: plain soft-threshold at `lam_s/mu` | baseline `S` — *not* SS-RTD's TV-smooth `S` |
| `ssrtd_n_sparsity`, `ssrtd_n_nonzero_pct` | the baseline's `N`: plain soft-threshold at `lam_n/mu` | baseline `N` — has **no** counterpart in SS-RTD (its `E` is L1 noise, a different role) |
| `ssrtd_winner` | which of the baseline's `S`/`N` absorbed the foreground | baseline winner |
| `ssrtd_time_s` | baseline runtime | baseline runtime |
| `N_ssrtd_kb` | H.264 size of the baseline's `N` | baseline `N` size |
| `hybrid_*` | Tensor-RPCA `L` + baseline `N`, recombined | hybrid (negative result) |
| `hybrid_compression_ratio` | unaudited denominator (§3) | **do not quote until audited** |

**`param_sweep.csv`**

| Archived column | What it actually is |
|---|---|
| `lam_s`, `lam_n`, `config` | the baseline's two soft-threshold weights and the five configs of §3.2 — the baseline has two parameters; SS-RTD has one |
| `s_nonzero_pct`, `n_nonzero_pct`, `winner` | the baseline's `S`/`N` occupancy and which one won |
| `recon_error`, `n_iter`, `runtime_min` | baseline constraint residual, iteration count, runtime |

Anything written by Phase 3 uses the new names from the output contract
(`IMPLEMENTATION_PLAN.md`): a `method` column, and `L`/`S`/`E` columns for real
SS-RTD, never the `ssrtd_*` prefix.

### Required before any new run — status

1. ✅ **Copy both CSVs off this disk.** Done 2026-09-09 to OneDrive; hashes
   re-verified 2026-09-18. `results/figures/` was not copied — see the warning above.
2. ✅ **Snapshot the baseline under a distinct path.** Done:
   `results/baseline_naive/`, which no pipeline writes to.
3. ⏳ **Point the new implementation at new filenames with an explicit `method`
   column.** Specified as the binding **output contract** in
   `IMPLEMENTATION_PLAN.md`, and not yet exercised — Phase 3 has not run. The
   runner must also key its resume check on the new file:
   `src/batch_runner.py` hard-codes `all_results.csv`, and pointed there it would
   see all 180 baseline rows and skip every video (`PHASE3_NOTES.md` §3).
