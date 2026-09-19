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

> ✅ **RESOLVED 2026-08-30 — see §4 item 1.** This flag originally read "UNVERIFIED:
> the attribution 'Shen et al. 2022'", because no citation, DOI or bibliography
> existed anywhere in the repo. The paper is now in hand and pinned down:
> **Shen et al., IEEE TASE vol. 20 no. 1, pp. 583-596, 2022,
> DOI 10.1109/TASE.2022.3163674**, with its equations transcribed and
> cross-checked against rendered page images in
> [`paper/SOURCE.md`](paper/SOURCE.md). The comparison it made possible is §4
> item 1: `src/ssrtd.py` is **not** that method, so the "generic three-component
> tensor RPCA variant" wording above understates it — it is a different algorithm,
> not a partial implementation.

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
   *Status updated 2026-09-18.* Original list: the manuscript, `README.md`,
   `CLAUDE.md`, the `ssrtd_*` column names in both CSVs, and the `ssrtd.py`
   module docstring; plus a replacement name for the algorithm we actually ran,
   which is not in the literature under any name.

   | Artifact | Status | Auto-loads? |
   |---|---|---|
   | `CLAUDE.md` | ✅ done, commit `9dc2ef3` — rewritten to the post-pivot framing; the two flagged lines no longer exist | yes |
   | `README.md` | ⏳ pending — still says "SS-RTD's three-component decomposition (smooth + sparse + residual)" and labels `ssrtd.py` as "SS-RTD implementation" (lines 11-12, 19, 35, 58) | no |
   | `ssrtd_*` column names in both CSVs | ✅ **decided 2026-09-18: do NOT rename.** The archived CSVs are immutable — all three copies are verified byte-identical by SHA256, and renaming in place would invalidate that and require redoing every copy. The terminology mapping is recorded in `ARCHIVE_BASELINE.md` §6; new terminology is applied in the analysis and figure scripts that *read* the files, never in the stored data | no |
   | `src/ssrtd.py` module docstring | ⏳ pending — still reads "SS-RTD modified for surveillance video — smoothness penalty removed" and repeats the retracted overflow claim (lines 46-57); stale `lam_s`/`lam_n` defaults in the parameter block too | no |
   | The manuscript (Overleaf) | ⏳ Phase 5 | no |
   | A real name for the baseline | ⏳ Phase 2 | no |

   Revisit the pending rows before the paper's final repo state. None of them
   auto-loads, so none can mislead a session the way `CLAUDE.md` could.

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

## 6. Verification gate (g2) — outcome, 2026-09-13

**Both E-threshold factors PASSED.** Real SS-RTD (`src/ssrtd_real.py`) reproduces the
paper's Fig. 3 behaviour on the paper's own data. Phase 1 is complete and VIRAT runs are
no longer gated. Run: `python -m src.gate_candela --factor both` at commit `a796ae6`;
outputs in `results/gate_candela/`, log in `logs/gate_candela_factor_both.log` (both
gitignored, about 30 minutes to regenerate). Criterion-by-criterion table in
`IMPLEMENTATION_PLAN.md` (g2).

Setup: SBI Candela, first 80 files of `Candela_m1.10.zip` (original frames 85-164),
288x352 grey on the 0-255 scale, 10% random-valued impulse noise by replacement (seed 0),
lambda 0.4, 100 iterations. Neither run reached the 1e-6 tolerance; the paper's Fig. 3
also spans 100 iterations.

### 6.1 Factor choice: `factor = 1.0` for VIRAT

Both factors pass, but factor 1.0 is closer to the paper on nearly every paper-derived
measure:

| | factor 1.0 | factor 2.0 |
|---|---|---|
| Average gap from the 39 digitized Fig. 3 points | **0.0030** | 0.0040 |
| relChg_S at iterations 30 / 50 (paper 0.0099 / 0.0029) | **0.0100 / 0.0033** | 0.0146 / 0.0055 |
| Final relErr_L (paper ~0.0125 in Fig. 3, 0.013 in Fig. 4) | **0.0137** | 0.0140 |
| Standard PSNR vs Table I's 43.27 dB | **42.83** | 42.66 |
| Final constraint residual err_X | **79.7** | 280.5 |
| E nonzero (10% of pixels actually corrupted) | 74.6% | **38.4%** |
| Share of E's nonzeros that are real noise | 0.134 | **0.258** |

relChg_S is the most discriminating curve: factor 1.0 follows Fig. 3 almost point for
point, while factor 2.0 lags. Factor 1.0 is also the value Appendix A's eq. (17) implies
(`PAPER_NOTES.md` item 11), so the paper's own data and its own derivation agree.

**Decision: factor 1.0 for all VIRAT runs.** This suggests the authors' code used
`1/beta_X` and eq. (12)'s printed 2 is a typo. That is supporting evidence, not proof:
both factors pass, and factor 2.0 gives a sparser, more precise E. Neither E is as sparse
as the injected noise; E also absorbs non-noise detail.

⚠️ The code default `E_THRESHOLD_FACTOR` is still 2.0 (the printed value). Phase 3 must
pass `factor=1.0` explicitly.

### 6.2 The SBI subset is confirmed as the paper's input

relErr_L at iteration 1 is **0.0628 against the paper's 0.0626**. At iteration 1, L is
just the Tucker approximation of the noisy input, before any ADMM update, so this value
depends only on the frames, noise level, grey conversion and ground truth — not on the
solver. The match confirms that the first 80 files of SBI's subset (original frames
85-164) are the paper's actual input, on top of the documentary evidence recorded at
`SBI_SUBSET_FRAMES` in `src/gate_candela.py`.

### 6.3 Open observation: relChg_L mid-run gap (unexplained)

For both factors, relChg_L levels off near **0.010 between iterations 15 and 40**, where
Fig. 3 has it falling to about 0.002 by iteration 30 — roughly **5x the paper's value**
over that stretch. It decays by the end (factor 1.0: 0.0010 at iteration 80 against the
paper's 0.0005, and 0.0002 at 100), so C3b passes. The gap is larger than the ~0.003
accuracy of reading values off the plot, so it is not a digitization artifact.

**Not explained.** Possible causes, none tested: HOOI details the paper does not specify
(how the 20 inner iterations are initialized at each outer iteration, or whether they
warm-start), or a difference in how the authors computed relChg_L. Does not block Phase 3,
but should be reported alongside the Fig. 3 reproduction rather than omitted.

### 6.4 Measured resources, and the VIRAT projection

| | factor 2.0 | factor 1.0 |
|---|---|---|
| Wall time, 100 iterations | 14.2 min | 15.0 min |
| Per iteration | 8.55 s | 8.99 s |
| Peak working set | 2,008 MB | 2,541 MB |

Candela is 288x352x80 = 8.1M elements; VIRAT is 180x320x300 = 17.3M, about 2.1x larger.
Linear scaling projects **~18-19 s per iteration and a 4.3-5.4 GB peak** per VIRAT
video — **tight on the 8 GB machine** — and, at 100 iterations, **~31 min per video and
~90 h for all 180**. VIRAT's lower Tucker ranks (144 vs Candela's 231) may bring the time
down. These are estimates: measure on the first VIRAT video before starting the batch.
The memory plan is unchanged — try `rfftn` first, float32 only if needed
(`IMPLEMENTATION_PLAN.md` (g), carry-forward decision 3).

### 6.5 Table I comparison (reported only)

Standard PSNR 42.83 dB (factor 1.0) / 42.66 dB (factor 2.0) against Table I's 43.27 —
within 0.44 / 0.61 dB. The formula as printed would give -7.2 / -7.4 dB on the same
result, confirming `PAPER_NOTES.md` item 15 on real data. SSIM 0.9939 / 0.9937 against
Table I's 0.9019; the likely explanation is in `PAPER_NOTES.md` item 17.

---

## 7. Phase 3 preflight — first measured full-ADMM run on VIRAT, 2026-09-19

`python -m src.measure_virat_one` on `video_01` (`180x320x300`, [0,1] scale), real
SS-RTD with `lam = 0.4`, `factor = 1.0`, 100 iterations, launched detached, at
commit `463de7e` (the `rfftn` change). Outputs in `results/scratch/measure_virat_one/`
(gitignored; `summary.json`, `history.csv`, `components.npz`,
`decomposition_frame.png`), log in `logs/measure_virat_one.log`. Peak memory is
psutil's `peak_wset` — tracked by the OS, not polled.

### 7.1 Memory and time: measured against the projection

| | Projected | **Measured** |
|---|---|---|
| Peak working set | 4,300–5,530 MB | **3,512 MB** (final 1,463 MB) |
| Wall clock, 100 iterations | ~31 min | **35.9 min** (21.5 s/iter mean) |
| Per iteration | 18–19 s | median **19.8 s**, min 13.5, **max 48.2** |

Memory came in 0.8–2.0 GB **under** the projection: the `rfftn` change did more in
the full loop than the S-update probe showed (probe peak 2,840 → 2,491 MB; full loop
never reached the projected range). Time came in 16% **over**, and the profile says
why (7.2).

### 7.2 The machine pages around the peak — that is the time overrun

Fifteen iterations exceeded 25 s, **all between iterations 6 and 31**, while the
working set climbed to its 3.5 GB peak; after iteration 31 none did. Checked live
at iteration ~35:

- machine **7,971 MB** total, **1,455 MB** physical free
- **commit charge 15,960 / 17,081 MB (93%)** — the pagefile nearly full
- **430–1,490 pages/sec** during the burst
- no competing load: the largest other processes were ~250 MB

So the process fits, but the *machine* was paging at the peak with about **1.1 GB
of commit headroom**. A modest extra spike would be a `MemoryError` mid-batch.
**Consequence:** the `tv_adjoint` temporary (`beta_f * f - mult_f`, 396 MB) and the
three `tv_forward(S)` allocations per iteration (396 MB each, in `update_f`,
`primal_residuals`, `update_multipliers`) are now required levers, not optional
ones. Planned as separate, individually tested changes.

### 7.3 Batch implication

**180 videos × 35.9 min ≈ 108 h**, before H.264 encoding, at 100 iterations. The
run did not reach `tol = 1e-6` (`relChg_E` 4.1e-3 at iteration 100) — same as both
Candela runs — so the 100-iteration cap governs, and `max_iter` is the batch's
time knob. Per-video timeout in the old runner is 3,600 s; 36 min fits, but the
48 s iteration spikes show the margin is thin under paging.

Convergence was healthy: `err_X` 177 → 0.58, constraint residual 0.027% of ‖X‖,
`beta_X` grew on 40/100 iterations to 236, `beta_f` to 7,815.

### 7.4 First look at the research question — S and E share the edges

**One video, one lambda, first look: not a result.** Frame 151 of `video_01`
(`decomposition_frame.png`):

- `L` is a clean empty-plaza background, as it should be.
- `E` is **edge residue, not noise.** VIRAT has no injected impulse noise, so `E`
  has nothing designated to absorb; it lands on the sharp structural edges of the
  *background* — umbrella rims, stair treads, railings. 82% of pixels nonzero,
  only 6.6% above 0.05.
- `S` is **not a clean smooth foreground.** The people on the stairs are visible as
  blobs, but `S` also carries a broad ±0.02 field over the whole frame and the same
  background edge structure `E` has. Only 4.0% of pixels exceed 0.05, and **45% of
  those also have `|E| > 0.05`** — the two components share the sharp edges rather
  than separating.

If this holds across videos and across `lambda` in [0.2, 1], it is the
smooth-vs-sharp finding the pivot exists to test: the TV-smooth `S` does not
cleanly capture sharp surveillance foreground, and the edges leak into both `S`
and `E`. Phase 3 is what establishes it. Caveats that stand until then: single
video; `lambda = 0.4` only; clean input with no noise for `E` to do its designated
job (see the open question below); no ground truth.

**Open question (raised 2026-09-19, not yet decided):** on Candela the paper injects
10% impulse noise, so `E` has a defined role; on clean VIRAT it has none. Whether
that makes the clean-input condition unfair to the method, and whether Phase 3
needs a noise-injected VIRAT condition alongside the clean one, is to be settled
before the batch is designed.

### 7.5 Memory levers A–D: same numbers, 3,187 MB and 21.4 min (run 2, 2026-09-19)

Four allocation-only changes, each its own commit, each gated on **bitwise**
reproduction of a reference computed with the pre-lever solver (commit `a131d7c`,
stored in `src/testdata/ssrtd_real_reference_a131d7c.{npz,json}`, checked by
`test_ssrtd_real` test 7 on four synthetic runs, 25–60 iterations). Every number the
solver produces is unchanged; only the allocations are.

| Lever | Commit | What changed |
|---|---|---|
| A | `0be5c23` | `update_f` thresholds `A` in place (`soft_threshold_inplace`, `tensor_rpca.py`; `A += 0.0` first so `-0.0` inputs match `np.sign`) |
| B | `140c759` | `tv_forward(S)` once per iteration, passed as `DS` to `update_f`, `primal_residuals`, `update_multipliers`; one-temp `mult_f` line |
| C | `5092863` | `tv_adjoint_affine(beta_f, f, mult_f)` accumulates per component; no `(3,H,W,T)` `beta_f*f - mult_f` temporary |
| D | `98be388` | `X_tilde` freed after HOOI; `L_prev`/`S_prev` freed right after their `relChg` |

Run 2 (`results/scratch/measure_virat_one_after_levers/`, commit `98be388`), same
video, same settings as run 1:

| | Run 1 (`463de7e`) | **Run 2 (`98be388`)** |
|---|---|---|
| Peak working set | 3,512 MB | **3,187 MB** |
| Wall clock, 100 iterations | 35.9 min | **21.4 min** (12.87 s/iter mean) |
| Per iteration | median 19.8 s, max 48.2 | median **12.4 s**, max **15.0**, none above 25 s |
| Commit charge at peak | 93% (1,455 MB free) | 87% (2,142 MB free at iter ~12) |

`history.csv` and the final `L`, `S`, `E` are **bitwise identical** between the two
runs (`relErr_L` is all-NaN in both — compare with `equal_nan`). The 40% time saving
is the paging going away plus the two dropped `tv_forward` calls, not any change in
arithmetic. Peak fell only 325 MB, because A–D mostly cut non-peak stages; the
per-stage profile (7.6) found where the peak actually is.

### 7.6 Per-stage profile after A–D: the multiplier update is the peak

One full-size iteration (`180x320x300`), `tracemalloc` with `reset_peak()` between
stages, numpy allocations only (the OS working set adds interpreter + BLAS buffers):

- **Resident loop state: 1,517 MB** — `X, L, S, E, mult_X` (5 × 132 MB), `f, mult_f`
  (2 × 396 MB), `phi` 66 MB, `E_prev` 132 MB, HOOI factors.
- Transients above resident: `compute_phi_half` 923 MB (once, at init), `X_tilde` 396,
  HOOI 306, `update_S` 659, `tv_forward → DS` 791, `update_f` 791 (on 1,781 resident
  incl. `DS`), `update_E` 527, `primal_residuals` 396, **`update_multipliers` 1,055 MB
  on 1,913 resident → ~2.97 GB, the peak stage**, log row 396.

The multiplier stage peaks because the old and new `mult_f` (396 MB each) coexist
while the chained `X - L - S - E` builds three `(H,W,T)` temporaries. `update_f`
and `DS` still stack three rolls before differencing. These are lever E (7.7).

### 7.7 Lever E: peak 2,663 MB, same numbers (run 3, 2026-09-19)

Commit `342e4d5`, four more allocation-only changes in `src/ssrtd_real.py`, gated the
same way (bitwise reference, new bitwise tests in three suites, 248 assertions):
`update_multipliers(inplace=True)` for the loop (chained `X - L - S - E` in one
temporary; multipliers overwritten instead of old/new pairs coexisting; default
stays non-mutating), per-component `soft_threshold_inplace` in `update_f`,
`tv_forward_into` writing `DS` one roll at a time, and per-component
`compute_phi_half`.

Run 3 (`results/scratch/measure_virat_one_after_lever_E/`, log
`logs/measure_virat_one_after_lever_E.log`), same video and settings:

| | Run 1 `463de7e` | Run 2 `98be388` | **Run 3 `342e4d5`** |
|---|---|---|---|
| Peak working set | 3,512 MB | 3,187 MB | **2,663 MB** (final 1,479 MB) |
| Wall clock, 100 iterations | 35.9 min | 21.4 min | **21.9 min** |
| Per iteration | mean 21.4 s, max 48.2 | mean 12.7 s, max 15.0 | mean **13.0 s**, median 12.3, max 18.1, none > 25 s |

All three runs agree **bitwise** on every `history.csv` column except `seconds` and
on the final `L`, `S`, `E` (`components.npz`). Lever E is a memory lever only — the
0.5 min wall-clock difference against run 2 is run-to-run noise.

**Where this leaves the batch.** Peak is now 849 MB below run 1 and about 0.85 GB
under the ~3.5 GB at which this machine paged, so commit headroom during the batch
is roughly 2 GB instead of 1.1 GB. That meets the target set for this work (peak
comfortably below ~2.6 GB — 2,663 MB is at the line, with the working-set number
including ~200 MB of interpreter and BLAS overhead the numpy profile does not
count). Time: **180 videos × ~22 min ≈ 66 h** at 100 iterations, before H.264
encoding, against the 108 h projected from run 1. float32 remains unnecessary;
HOOI warm-starting remains off (it would change the numbers). The memory work is
closed; the next step is the Phase 3 batch runner.

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
