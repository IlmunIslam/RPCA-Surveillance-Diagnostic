# RESEARCH LOG — RPCA Surveillance Diagnostic

> Authoritative record of what was actually built and run. Every claim below is
> tagged with the file:line or data file it was verified against. If a statement
> here has no source tag, treat it as unverified.
>
> Created 2026-08-29. Repo root: `RPCA_Surveillance_Diagnostic/` (renamed from
> `RPCA_Hybrid_Project/` on 2026-09-09 to match the GitHub repo name; the parent
> folder `Video compression Research/` is *not* under version control).

---

## 1. What the code ACTUALLY implements (verified from source, not assumptions)

### `src/ssrtd.py`
Three-component ADMM decomposition `X = L + S + N`:
- `L` via `tensor_svt` — SVD soft-threshold on all 3 mode-unfoldings, refolded and
  averaged (`ssrtd.py:29-39`)
- `S` via `soft_threshold` at `lam_s / mu` (`ssrtd.py:87`)
- `N` via `soft_threshold` at `lam_n / mu` (`ssrtd.py:88`)
- Dual update `Y += mu * (X - L - S - N)`, `mu *= 1.5` capped at 1e6 (`ssrtd.py:89-90`)

**CRITICAL: NO smoothness penalty is implemented. It was never in the code.**
The docstring at `ssrtd.py:48` and `ssrtd.py:55-57` says "smoothness penalty
removed", but the git history shows it was never present to remove:
- `d7a786e` (2026-06-07) is the commit that *creates* `src/ssrtd.py`, and the
  added lines already contain the "removed" docstring and the same three-update
  loop in use today. There is no prior version.
- Only **two blobs** of `src/ssrtd.py` have ever existed (`ffdce15`, `cfbd7ea`);
  the `ffdce15` loop body is identical apart from lambda defaults.
- Pickaxe `git log -S` over all history: `smooth` hits only `CLAUDE.md`/`README.md`
  prose; `lam_t` and `total_variation` hit nothing. No stash, no other branches,
  no dangling objects (`git fsck` clean).
- The earliest trace of the decision predates the module: `CLAUDE.md:30` in the
  **initial** commit `6a7878e` already reads
  `"SS-RTD: lam_s=0.001, lam_n=0.002, smoothness penalty REMOVED (caused overflow)"`.

So the "float64 overflow on sharp-edged foreground" rationale in the docstring is
**an undocumented claim with no artifact in this repo** — no code, no log, no
failing run. It may be true, but nothing here evidences it.

**What we therefore actually have:** a generic three-component tensor RPCA variant
(low-rank + two independently-thresholded sparse terms). It is NOT the full SS-RTD
method from the source paper.

> ⚠️ UNVERIFIED: the attribution "Shen et al. 2022". No citation, bibliography,
> DOI, or arXiv reference exists anywhere in this repo (`paper/` and `notebooks/`
> are both empty). The exact paper being claimed as the baseline needs to be
> pinned down and added here before any writeup — the collapse finding is only
> meaningful relative to a specific, named formulation.

### `src/tensor_rpca.py`
Two-component `X = L + S` via ADMM (`tensor_rpca.py:48`). Same `tensor_svt` helper
(duplicated, not imported — kept independent per the comment at `ssrtd.py:9`).
Default `lam = 1/sqrt(max(H, W))` (`tensor_rpca.py:66-67`); the pipeline calls it
with defaults (`run_pipeline.py:90`).

### Parameters used in the main 180-video batch
`lam_s=0.01, lam_n=0.001` — **confirmed**, passed explicitly at
`run_pipeline.py:108`, not inherited from any default.

### ⚠️ Latent inconsistency: `run_ssrtd()` defaults
`run_ssrtd()` (`ssrtd.py:119`) defaults to `lam_s=0.001, lam_n=0.002` — both
different from and **ratio-inverted** relative to the tuned `ssrtd()` defaults
`lam_s=0.01, lam_n=0.001` (`ssrtd.py:46`). Commit `75fa46f` updated the signature
defaults but left `run_ssrtd`, and the docstring at `ssrtd.py:62-63`, on the old
values.

This is latent, **not active**, for one reason: `run_ssrtd()` has **zero callers**
anywhere in the repo (grep across `*.py`, `*.ipynb`, `*.ps1`, `*.md` returns only
its own definition). It is dead code. Nothing in `all_results.csv` was produced
through it.

Severity is high despite being dormant: per §3.2 the lambda *ratio* alone decides
the outcome, and the `run_ssrtd` ratio (`lam_s < lam_n`) is the one that makes **S
win** — the opposite of every result on record. Anyone who calls this function
expecting the production configuration will silently get an inverted decomposition.

### ⚠️ PSNR/SSIM columns do not measure reconstruction quality
`ssrtd_psnr` compares the original frames against `L + S + N`
(`run_pipeline.py:111-112`), and `tensor_psnr` against `L + S`
(`run_pipeline.py:93-94`). Since the ADMM constraint *is* `X = L + S + N`, this
measures the converged constraint residual, not video quality — which is why the
values are physically meaningless as quality scores (median `ssrtd_psnr` **217.4 dB**,
`tensor_psnr` **205.5 dB**, SSIM pinned at 1.0). Only `hybrid_psnr` (median
**30.70 dB**) and the `*_after_h264` columns measure anything lossy.

---

## 2. Known issues found (reviewer critique, 4.5/10, major revision)

<!-- PLACEHOLDER — paste the full review text here. -->

_# Critical Review: "Component Collapse in Three-Component Tensor Decomposition for Surveillance Video Compression"

## 1. Novelty

The paper's core contribution is a **negative/diagnostic finding** rather than a new method: SS-RTD's third component (N) does not provide genuine separation on surveillance video — it either absorbs the entire foreground or nothing, and which happens is dictated by the λ ratio, not the scene. This is a legitimate and useful empirical observation, and negative results of this kind are undervalued in the literature, so there is real value here.

However, the novelty is more modest than the framing suggests:

- The "binary collapse across 180 videos" (Contribution 1) and "parameter controls the winner" (Contribution 2) are **not independent findings**. The 180-video experiment uses a single fixed setting (λs=0.01, λn=0.001, i.e., λs > λn), which the parameter-sweep result already predicts must produce an N-win. So Contribution 1 is essentially a large-N confirmation of the mechanism already established in Contribution 2, not a separate discovery. Presenting them as two distinct bullet-point contributions somewhat inflates the paper's apparent scope.
- The mechanism itself (whichever soft-thresholding penalty is smaller absorbs the signal) is a fairly predictable consequence of how ADMM-based sparsity penalties work; the paper doesn't derive this from first principles, but it also isn't a surprising phenomenon to anyone familiar with proximal/soft-thresholding operators.
- Generalization is based on exactly **one** three-component method (SS-RTD). The claim "the third component is of no benefit" is stated generally in the implications section but is only demonstrated for SS-RTD, not for the broader family of three-component methods the introduction references (e.g., [6]).

## 2. Problem Statement

The motivation (storage costs, redundancy, RPCA background/foreground separation) is reasonable and clearly laid out. But there's a conflation of two distinct questions that the paper answers with one dataset and doesn't clearly separate in the framing:

1. Does SS-RTD's third component meaningfully separate foreground/noise on surveillance video?
2. Does RPCA-style decomposition help compress surveillance video relative to H.264?

These are related but logically separate, and the paper would be clearer if it stated them as two explicit research questions rather than blending them into a single narrative that jumps from decomposition behavior to compression benchmarking.

## 3. Consistency of Methodology

This is where the paper has its most serious issues.

**Modifying the method under test undermines the central claim.** The paper disables SS-RTD's smoothness penalty on S because it causes float64 overflow on sharp-edged surveillance foreground. But the smoothness penalty is a defining structural component of SS-RTD — it's precisely the mechanism that would push some content into S in a spatially-coherent way rather than letting one term win by threshold size alone. Removing it and then concluding "SS-RTD collapses to two components on surveillance video" is not fully justified — what's actually being shown is that **a smoothness-penalty-free variant of SS-RTD** collapses. It's plausible (even likely) that the smoothness term itself is what prevents/attenuates the winner-take-all dynamic in the original formulation, meaning the paper may be characterizing an artifact of their fix rather than an intrinsic property of SS-RTD. This should have been addressed with an alternative fix (e.g., gradient clipping, rescaling, a bounded smoothness penalty) and a comparison, or at least flagged as a first-order limitation rather than tucked into the methodology section as a one-line implementation detail.

**Promised metrics never reported.** PSNR and SSIM are explicitly introduced in the methodology ("Reconstruction quality is assessed using PSNR and SSIM") but **never appear in the Results section**. Given that the paper's compression claims (L beats H.264 by 6.8%) are meaningless without knowing whether reconstruction quality is preserved, this is a significant gap — readers cannot tell if the compression gains come at a fidelity cost.

**Parameter granularity is too coarse to fully support the "no middle ground" claim.** The five configurations tested differ by roughly 2x to 10x in λ ratio, plus one exact-equality case. There's no test near the boundary (e.g., λs=0.0011 vs λn=0.001) to confirm the transition is a genuine discontinuity rather than a steep-but-continuous function that just looks binary at the tested resolution.

## 4. Do the Experiments Actually Support the Claims?

- **Collapse finding**: Reasonably well supported for the specific (ablated) SS-RTD variant and specific parameter regime tested, across a genuinely large sample (180 videos) — this is a strength.
- **Parameter-control finding**: Well supported within the tested configurations (100 video-configuration trials, unanimous), though the sample of videos (20) and configurations (5) is small relative to the 180-video headline number, creating an asymmetry between the two "contributions."
- **Compression finding**: This is the weakest empirical claim as framed. "L beats H.264" compares a **background-only** stream (mostly static, by construction highly compressible under H.264's temporal prediction) against a baseline that encodes the **full video including motion**. This comparison is close to tautological — a nearly static signal will almost always compress far below a signal with motion, regardless of the decomposition method's merit. The paper doesn't make explicit what use case this result is meant to support (L alone discards the foreground content that is usually the entire point of a surveillance video), so the practical implication of "focus on the background, not on splitting out foreground streams" is questionable when the foreground is presumably the information of interest. The more genuinely interesting and rigorously supported result — that the hybrid L+N reconstruction never beats H.264 — is arguably the paper's strongest and most useful finding, but it's given less emphasis than the weaker L-only result.
- No variance/error bars or significance testing anywhere (only min/mean/max), which is a minor but avoidable gap given the sample sizes involved.

## 5. Major Problems

1. Testing a modified (smoothness-penalty-removed) version of SS-RTD and generalizing conclusions to "SS-RTD" without adequately isolating whether the modification itself causes the collapse.
2. PSNR/SSIM promised in methodology but absent from results — a direct methodology/results mismatch.
3. The headline compression comparison (L vs. H.264 baseline) compares non-equivalent content (static background vs. full video with motion), which weakens the practical meaning of the 6.8% figure.
4. Redundancy between the two headline "contributions" (180-video collapse and 20-video parameter sweep), which are mechanistically the same finding at different scales rather than independent evidence.
5. Generalization claims ("the third component provides no benefit" for three-component methods broadly) are based on a single method (SS-RTD), a single dataset (VIRAT outdoor), reduced resolution (320×180), and short clips (300 frames) — all narrower than the language of the implications section suggests.

## 6. Minor Problems

- Table II rows are listed out of numeric order (1, 3, 5, 2, 4) without explanation.
- Sparse related-work section (7 references) for a paper making fairly general claims about "three-component tensor decomposition" methods as a class.
- Some awkward phrasing in the introduction (e.g., "This technique was first introduced by Robust PCA (RPCA)" reads oddly since RPCA is being used both as the technique and its origin).
- No discussion of computational cost/runtime, which would matter for a compression-pipeline paper.
- No sensitivity analysis on frame count (300) or downsampling resolution (320×180) despite these being flagged as limitations that could plausibly affect the central finding.
- CRF settings (23 vs. 28) are introduced but it isn't clear which is used for the headline 6.8% number, or whether both were tested and averaged.

## 7. Score and Verdict

**Score: 4.5 / 10** (workshop/short-paper standard)

**Verdict: Major revision required, not ready for acceptance as-is.**

The paper asks a worthwhile question and the underlying phenomenon (parameter-driven winner-take-all in a soft-thresholded decomposition) is very plausibly real and worth reporting — negative results like this are useful to the community. But the current draft has a methodology-altering modification to the very method it studies without adequately isolating its effect, omits results for metrics it promised to report, and its flagship compression claim rests on a comparison (background-only vs. full video) whose fairness is questionable. The two headline contributions are also more overlapping than the framing implies. With (a) a proper treatment or discussion of the smoothness-penalty removal's effect on the conclusion, (b) actual PSNR/SSIM numbers, and (c) a clearer articulation of what the L-vs-H.264 comparison is meant to demonstrate (or a fairer reconstruction-quality-matched comparison), this could become a solid, useful short paper._

---

## 3. Experiments completed

### 3.1 — 180-video batch → `results/metrics/all_results.csv`
- **Scale:** 180 rows, 180 unique videos, 28 columns. Processed
  2026-06-22 03:48 → 2026-06-28 09:42.
- **Driver:** `src/run_pipeline.py::process_video`, batched by `src/batch_runner.py`
  (resumable, per-video error isolation + timeout).
- **Input:** first 300 frames per video, grayscale `(H, W, T)` in [0,1]
  (`run_pipeline.py:80`). VIRAT Ground 2.0, videos-01 subset.
- **Methods per video:** (a) Tensor RPCA, default lambda; (b) SS-RTD,
  `lam_s=0.01, lam_n=0.001`; (c) Hybrid = `build_hybrid(L_tensor, N_ssrtd)` —
  Tensor-RPCA background + SS-RTD movement carrier (`run_pipeline.py:136`);
  (d) H.264 compression measurement.
- **Headline result — S collapse is total and unanimous:**
  `ssrtd_winner == "N"` in **180 / 180** videos. Median `ssrtd_s_nonzero_pct`
  **0.10%** (range 0.02–0.56%); median `ssrtd_n_nonzero_pct` **99.95%**
  (range 99.87–99.99%). S is empty; N carries everything.
- **No scene dependence:** foreground density spans 0.0127–4.263 (median 0.3047),
  a 335× range, with zero effect on the winner. The `foreground_density`
  diagnostic (`metrics.py:compute_foreground_density`), added to predict collapse
  direction, has **no predictive power** — the outcome is constant.
- **Hybrid:** median PSNR 30.70 dB (28.75–32.60), median SSIM ~0.956.
- ⚠️ Not yet verified: the exact denominator behind `hybrid_compression_ratio`
  (median 0.4773) — defined in `src/compression.py`, not audited for this log. In
  spot-checked rows `hybrid_kb` **exceeds** `original_comp_kb` (e.g. video_02:
  100.57 vs 56.43 KB), i.e. the hybrid encodes *larger* than the plain H.264
  reference. Treat the compression result as a negative one until confirmed.

### 3.2 — 20-video × 5-config parameter sweep → `results/metrics/param_sweep.csv`
- **Scale:** 100 rows = 20 videos × 5 configs. Processed 2026-07-01 09:36 →
  2026-07-04 03:07. Driver `src/param_sweep.py` (resumable; SS-RTD only — no
  Tensor RPCA, no compression; tensor built once per video and shared across the
  5 configs).
- **Video selection:** 20 videos spaced across the foreground-density range,
  over-weighting the busiest scenes (`param_sweep.py:48-54`). Density span
  0.0127–4.263.
- **Result — the winner is decided by the lambda ratio alone, unanimously:**

  | config | lam_s | lam_n | ratio | winner | median S nonzero | median N nonzero |
  |---|---|---|---|---|---|---|
  | config_1 | 0.001 | 0.002 | `lam_s < lam_n` | **S** 20/20 | 99.94% | 0.00% |
  | config_2 | 0.002 | 0.001 | `lam_s > lam_n` | **N** 20/20 | 54.65% | 99.94% |
  | config_3 | 0.001 | 0.001 | **equal** | **S** 20/20 | 99.94% | 0.00% |
  | config_4 | 0.01 | 0.001 | `lam_s >> lam_n` (production) | **N** 20/20 | 0.14% | 99.94% |
  | config_5 | 0.001 | 0.01 | `lam_n >> lam_s` | **S** 20/20 | 99.94% | 0.00% |

  Every config is 20/20 unanimous. The component with the **smaller lambda** takes
  all the foreground; scene content never overrides it. Reconstruction error
  (~1.7e-07) and iteration count (32) are essentially identical across all five,
  so the decomposition is equally "converged" whichever way it collapses.
- **Note on the tie (config_3):** at `lam_s == lam_n` the split is not resolved by
  the data — S wins because S is updated before N in the loop
  (`ssrtd.py:87-88`), so S consumes the residual first. This is an update-order
  artifact, not a property of the video.

### 3.3 — Equal-lambda determinism check → `logs/test_equal_lambda.log`
- `src/test_equal_lambda.py`, `LAM_S = LAM_N = 0.001`, same video twice.
- Both runs identical: S nonzero **99.9106%**, N nonzero **0.0000%**,
  reconstruction error 2.297997e-07, converged in 32 iterations.
- **Verdict: deterministic.** The collapse is reproducible, not a numerical
  coin-flip. (Confirms the config_3 tie-break in §3.2 is systematic.)

---

## 4. Open problems / decisions pending

1. 🔴 **RESOLVED / CRITICAL — our code is not SS-RTD, and not a variant of it.**

   **Status: resolved 2026-08-30.** The source paper is now in hand:
   **Shen et al., 2022, IEEE Transactions on Automation Science and Engineering,
   DOI [10.1109/TASE.2022.3163674](https://doi.org/10.1109/TASE.2022.3163674).**
   This closes the UNVERIFIED citation flag in §1 and supersedes the old open
   items on the smoothness penalty. Equations (3)–(5), (8)–(14) and Algorithm 1
   were transcribed from the PDF and cross-checked against rendered page images
   on 2026-09-07; the verified transcription lives in
   [`paper/SOURCE.md`](paper/SOURCE.md). The PDF itself is gitignored — it
   carries an IEEE republication/redistribution notice and this repo is public.

   **The real SS-RTD objective (their eq. 5):**

   > minimize `||E||_1 + λ · ||S||_TV1`  subject to  `X = L + S + E`,
   > with `L` modeled by **Tucker decomposition**, ranks `r1 = 0.8H`, `r2 = 0.8W`, `r3 = 1`.

   Key facts from the paper:
   - **`S` (smooth foreground) is regularized by ANISOTROPIC TOTAL VARIATION**
     (their eq. 4) — *not* plain soft-thresholding.
   - **`E` (noise) is the sparse component**, via the L1 norm.
   - **`L` uses TUCKER decomposition via HOOI** — *not* tensor SVT.
   - **There is ONLY ONE tuning parameter `λ`**, recommended range **[0.2, 1]** —
     *not* two.
   - **The ADMM penalty parameters are ADAPTIVE and CONDITIONAL** (their eq. 14):
     `β ← c1·β` **only if** `Err(f^{k+1}) ≥ c2·Err(f^k)`, else `β` is left
     unchanged — with `c1 = 1.15`, `c2 = 0.95`, `γ = 1.1`. The penalty grows
     *only when the residual fails to shrink*, i.e. it responds to progress.

   **Term-by-term comparison against `src/ssrtd.py`:**

   | | Shen et al. 2022 (eq. 5) | `src/ssrtd.py` | Match |
   |---|---|---|---|
   | Low-rank `L` | Tucker via HOOI, ranks (0.8H, 0.8W, 1) | 3-mode SVT, refolded + averaged (`ssrtd.py:29-39`) | ❌ |
   | Smooth term | `λ · \|\|S\|\|_TV1`, anisotropic TV | *(absent)* | ❌ |
   | Sparse term | `\|\|E\|\|_1` | `soft_threshold(·, lam_s/mu)` (`ssrtd.py:87`) | ~ |
   | Second sparse term | *(none)* | `soft_threshold(·, lam_n/mu)` (`ssrtd.py:88`) | ❌ extra |
   | Tuning parameters | one, `λ ∈ [0.2, 1]` | two, `lam_s` + `lam_n` (0.01 / 0.001) | ❌ |
   | Penalty schedule | adaptive — grows only when the residual stalls (eq. 14) | fixed geometric ramp every iteration, `mu = min(mu*1.5, 1e6)` (`ssrtd.py:75,90`) | ❌ |
   | Stopping rule | rel. change in `E` < `1e-6`, `iter ≤ 100` (Alg. 1) | `tol=1e-7` on `L`, `max_iter=500` (`ssrtd.py:69`) | ~ |

   **CONCLUSION: `src/ssrtd.py` is NOT SS-RTD and is not a variant of it. It is a
   different algorithm.** Not one of the four defining elements — Tucker/HOOI
   low-rank, anisotropic-TV smoothness, single λ, adaptive conditional penalty —
   is present. **Every result labeled "SS-RTD" in the paper, in
   `all_results.csv`, in `param_sweep.csv`, and in the project docs is
   mislabeled.** Any claim about SS-RTD requires
   implementing the real method (their Algorithm 1) and re-running.

   **On the fourth divergence.** The first three differences are in the
   *objective* — we are minimizing a different function. The penalty schedule is
   different in kind: it is a difference in the *solver*, and it applies even
   where the objectives overlap. Their `β` is a feedback controller (grow only
   when `Err` stalls, eq. 14); our `mu` is an open-loop ramp that multiplies by
   1.5 every iteration regardless of whether anything improved, saturating at
   `1e6`.

   *Predicted consequence — arithmetic, not yet measured.* Frames are scaled to
   `[0,1]` (`preprocessing.py:22`) and `max(X.shape) = 320`, so
   `mu_0 = 1/(sqrt(320)·mean|X|)` ≈ 0.11–0.19 for typical grayscale means
   (0.3–0.5). Reaching the cap then takes `log(1e6/mu_0)/log(1.5)` ≈ **39–40
   iterations**. Past that point the effective soft-threshold radii `lam_s/mu`
   and `lam_n/mu` are ≈ `1e-8` — below the `1e-6` near-zero threshold
   `metrics.compute_sparsity` itself uses. If runs typically went well past ~40
   iterations, the `lam_s`/`lam_n` values we report as our tuned setting shaped
   only the opening ~8% of each run, and the rest was a near-hard constraint
   projection with the regularization effectively switched off. That would be a
   candidate mechanism for the winner-takes-all behaviour independent of the
   two-L1 argument below.

   *Blocker:* this cannot be checked from the existing data. `run_pipeline.py`
   computes `n_iter_ssrtd` but never writes it out — `all_results.csv` has 28
   columns and none of them is an iteration count. The iteration counts for the
   180-video batch are unrecorded. Testing this needs a re-run that logs `mu` and
   the iteration index per run.

   **Structural note (reasoning, not yet experimentally verified):** our two
   components `S` and `N` are *both* plain L1 soft-thresholds on the same
   residual. In the paper's terms we have **two copies of their `E` and none of
   their `S`** — the smooth term is missing entirely, and the "extra" component is
   a duplicate of the sparse one. Two interchangeable L1 penalties competing for
   one residual, differing only in threshold, is a formulation in which
   winner-takes-all is the expected outcome — which is exactly what §3.2 measures
   (100/100 runs decided by the λ ratio alone). Under the real objective the two
   non-low-rank terms are an L1 and a TV penalty, which are *not* interchangeable,
   and there is no ratio to tune because there is only one λ. **So the "collapse"
   is most likely a property of our formulation, not a finding about SS-RTD.**
   This must be confirmed against a real Algorithm 1 implementation before it is
   claimed either way — but it should not be assumed to transfer.

2. **Reframed (was item 1): the collapse question is no longer "SS-RTD vs. missing
   smoothness penalty."** Given item 1, the open question is now: does the
   winner-takes-all degeneracy occur in the *real* SS-RTD (Tucker + TV + single λ)
   at all? Requires implementing their Algorithm 1 and comparing against our
   `all_results.csv` numbers. Until that exists, no claim about SS-RTD as a
   published method is supportable.

3. **The headline batch used the single most collapse-forcing config.** The
   180/180 N-collapse in §3.1 was produced with `lam_s=0.01, lam_n=0.001` — which
   is exactly `config_4`, the config §3.2 shows drives foreground into N in 20/20
   videos by ratio alone. The unanimity is therefore partly *chosen*, not purely
   discovered. Any framing of §3.1 as evidence that "the method degenerates on
   surveillance video" must address that the same code with `lam_s < lam_n` puts
   99.94% of the signal back in S. Compounded by item 1: the method it allegedly
   degenerates is not the method named.

4. ~~**Pin down the baseline citation.**~~ **RESOLVED by item 1** — Shen et al.
   2022, IEEE TASE, DOI 10.1109/TASE.2022.3163674. The §1 UNVERIFIED flag should
   now be updated to point at item 1.

5. **Retract the overflow claim.** The docstring rationale (`ssrtd.py:55-57`) says
   a smoothness penalty was removed because it "causes float64 overflow." Per §1
   no such penalty was ever in this repo, and per item 1 the real smoothness term
   is anisotropic TV — which was never implemented, so it cannot have overflowed
   here. The claim has no artifact behind it and describes a removal that never
   happened. Delete it rather than trying to substantiate it.

6. **Fix the `run_ssrtd()` default mismatch** (§1). Dead code today, ratio-inverted
   relative to production, so it is a live trap the moment anyone calls it.

7. **Replace or relabel the tautological PSNR/SSIM columns** (§1). Reporting
   217 dB as a quality result would not survive review.

8. ~~**Confirm the compression result.**~~ **RESOLVED 2026-09-08 — not a bug, a
   reported negative finding.** The §3.1 caveat flagged that `hybrid_kb` exceeds
   `original_comp_kb` in spot-checked rows (video_02: 100.57 vs 56.43 KB) and
   asked whether the `hybrid_compression_ratio` denominator was wrong. It is not.
   The manuscript (`An_empirical_Study_on_VIRAT.pdf`, §IV-C and Table III) states
   this openly as a result: the hybrid **never** beats H.264 — 0/180 videos, and
   it runs **1.35x to 1.87x larger than baseline, mean 1.55x**. The spot-check
   ratio (100.57 / 56.43 = 1.78x) sits inside that reported range, so the data,
   the code and the paper agree. Nothing to fix.

   Two things this does *not* settle, kept here so they are not lost:
   `src/compression.py` is still unaudited, so the exact denominator behind the
   `hybrid_compression_ratio` median of **0.4773** remains unconfirmed — and a
   median *below* 1 reads as "smaller than reference", the opposite of the
   reported finding. That column is therefore probably measuring something other
   than hybrid-vs-baseline and should not be quoted until checked. Separately,
   the §2 reviewer critique rates this negative result the paper's *strongest*
   finding while noting it gets less emphasis than the weaker L-vs-H.264 claim —
   a Phase 5 framing issue, not a correctness one.

9. **Propagate the item-1 correction to every artifact that carries the label.**
   At minimum: the manuscript, `README.md`, `CLAUDE.md` (line 23 "SS-RTD — Smooth +
   Sparse + Residual Tensor Decomposition; subject of the collapse finding", and
   line 35 "smoothness penalty REMOVED"), the `ssrtd_*` column names in both CSVs,
   and the module docstring. Decide on a replacement name for the algorithm we
   actually ran — it needs one, since it is not in the literature under any name.

10. **Re-read the §2 reviewer critique in light of item 1.** The review was written
    while the method was still labeled SS-RTD, so its novelty and
    consistency-of-methodology sections assess a claim about a method we never ran.
    Several of its criticisms may be sharpened rather than answered by item 1 —
    the mislabeling is a more fundamental problem than anything the reviewer
    raised, and it was not available to them.

---

## 5. Implementation deviations from the paper (Phase 1 build)

Deviations forced during the faithful reimplementation of SS-RTD. Each one needs
to be stated in the methodology section of the rewritten paper — a deviation that
is not disclosed is the same class of error as the original mislabeling.

1. 🔶 **The paper's rank rule is mathematically infeasible for non-square frames.**
   *Found 2026-09-09 while building component (b); recorded 2026-09-10.*

   Algorithm 1 and §III-C specify `r1 = ceil(0.8H)`, `r2 = ceil(0.8W)`, `r3 = 1`.
   A Tucker multilinear rank triple is attainable only if
   `r_k <= prod_{j != k} r_j`, because the mode-`k` unfolding of
   `L = G x1 U1 x2 U2 x3 U3` is `U_k G_(k) (...)^T`, whose rank cannot exceed the
   product of the other two ranks. **With `r3 = 1` this reduces to `r1 <= r2` and
   `r2 <= r1`, i.e. `r1` must equal `r2`.** So the rule over-specifies `r2`
   whenever `H != W`.

   | Tensor | Paper asks for | Attainable |
   |---|---|---|
   | VIRAT, `180 x 320 x 300` | `(144, 256, 1)` | **`(144, 144, 1)`** |
   | Paper's own Candela, `288 x 352 x 80` | `(231, 282, 1)` | **`(231, 231, 1)`** |

   Intuitively: with `r3 = 1` every frame of `L` is a scalar multiple of one
   `H x W` image, and that image has rank at most `min(r1, r2)`. `r2 = 256`
   therefore describes nothing that `r2 = 144` does not already describe.

   **What we do:** `src/ssrtd_real.py:feasible_ranks()` clamps the requested
   triple to the attainable one and `hooi()` applies it internally.
   `tucker_ranks()` still returns the paper's literal `(144, 256, 1)` so the
   published rule stays visible in the code. Left unclamped, NumPy silently
   returns a `320 x 144` factor when asked for `320 x 256` — same numbers, but
   every downstream shape assumption is then wrong. Verified by
   `src/test_hooi.py` (22/22 assertions).

   **This is forced by mathematics, not chosen.** It does not change the
   decomposition numerically. It needs one sentence in the methodology.

2. 🔶 **`r3 = 1` makes frames proportional, not identical.** §III-C says r3 = 1
   is chosen "so that each image frame in `L` is the same [41]". Strictly,
   rank-1 in the temporal mode gives `frame_t = u3[t] * (one common image)` —
   frames are scalar *multiples* of each other, identical only when `u3` is
   constant. Measured frame-to-frame deviation on synthetic tests: **2.8e-2 to
   6.3e-2**, i.e. not identical. Minor, but it means any claim that `L` has
   literally constant frames is wrong; the correct statement is that `L` carries
   a single spatial pattern with a time-varying scale. `src/test_hooi.py` asserts
   the real invariant (mode-3 numerical rank 1) rather than literal equality.

---

## Verification provenance

Facts above were checked with, and are reproducible via:
- `git log --follow --oneline -- src/ssrtd.py`; `git show d7a786e -- src/ssrtd.py`
- `git rev-list --all --objects | grep ssrtd` (two blobs); `git cat-file -p ffdce15`
- `git log -S "smooth" --all`, `-S "lam_t"`, `-S "total_variation"`
- `git stash list`, `git branch -a`, `git fsck --lost-found --dangling` (all clean/empty)
- `grep -rn "run_ssrtd"` across `*.py *.ipynb *.ps1 *.md` (definition only, no callers)
- Column aggregates computed directly from `results/metrics/all_results.csv` (180 rows)
  and `results/metrics/param_sweep.csv` (100 rows)
