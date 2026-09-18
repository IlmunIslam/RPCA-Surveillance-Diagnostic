# PAPER NOTES — findings from the Phase 1 build that must reach the manuscript

> Running record. Every finding from the implementation that changes what the
> paper must say, filed under the section it informs, so nothing discovered
> during the build is lost before Phase 5 writing.
>
> **Append to this file as (e), (f), (g) are built.** Each entry should
> carry its source — the log entry, plan section or test that establishes it —
> so a claim in the manuscript can be traced back to something verified.
>
> **Item numbers are stable identifiers, not reading order.** New entries take
> the next free number and are filed under the section they inform, so a number
> cited elsewhere never changes meaning.
>
> Started 2026-09-13, after components (a), (b) and (c) were verified.

---

## For the Methodology section (deviations that must be disclosed)

1. **RANK RULE INFEASIBILITY.** The paper's rank rule
   (`r1 = ceil(0.8H)`, `r2 = ceil(0.8W)`, `r3 = 1`) is mathematically infeasible
   for non-square frames — `r3 = 1` forces `r1 = r2`. We clamp to attainable
   ranks: VIRAT (`180x320x300`) uses **`(144,144,1)` not `(144,256,1)`**. Forced
   by math, not choice. Needs one methodology sentence.
   *[RESEARCH_LOG.md §5 item 1; `src/ssrtd_real.py:feasible_ranks`;
   `src/test_hooi.py` test 5]*

2. **FRAME PROPORTIONALITY.** `r3 = 1` makes `L`'s frames scalar multiples of
   one common image (rank-1 in time), **not** literally identical as the paper's
   wording ("each image frame in L is the same") suggests. State that `L`
   carries a single spatial pattern with a time-varying scale.
   *[RESEARCH_LOG.md §5 item 2; `src/test_hooi.py` test 2 — measured frame
   deviation 2.8e-2 to 6.3e-2]*

10. **ANISOTROPIC VS ISOTROPIC TV IS AMBIGUOUS IN EQ. (10).** The paper's eq.
   (10) minimizes `lambda ||f||_q` with a **generic `q`**, which does not
   distinguish anisotropic TV (element-wise soft-threshold) from isotropic TV
   (per-voxel group shrinkage of `(f_h, f_v, f_t)` through a 2-norm). **Algorithm
   1 line 4 settles it** — "Updating `f` via (11) for anisotropic total
   variation" — as do the abstract and §III-C. We implemented the anisotropic,
   element-wise operator and verified it **differs measurably from isotropic
   group shrinkage** (max difference 0.7999 on a test case), so the choice is not
   cosmetic. Worth one methodology sentence, since a reimplementer reading only
   eq. (10) could reasonably build the other one.
   *[`src/test_f_update.py` test 4; `src/ssrtd_real.py:update_f`]*

11. 🔴 **THE SOURCE PAPER IS INTERNALLY INCONSISTENT ON THE E-UPDATE THRESHOLD.**
   *Rigor finding — the strongest one from the Phase 1 build.*

   **eq. (12) prints threshold `2/beta_X`** (verified against a rendered page
   image, because it looked unusual). **Appendix A's derivation implies
   `1/beta_X`.** Eq. (17) reduces the E-terms of the augmented Lagrangian to
   `min_E ||E||_1 + (beta_X/2)||A - E||^2` with
   `A = X - L - S - Lambda_X/beta_X`, whose proximal solution has threshold
   `1/beta_X` — the same pattern the paper itself applies in (16) -> (10) -> (11),
   where the threshold is `lambda/beta_f`.

   **Verified, not inferred:** the `(beta/2)` convention IS present in eqs (15),
   (16) and (17), so the factor 2 is *not* explained by an augmented-Lagrangian
   scaling that omits the one-half; (16) -> (11) uses `lambda/beta_f`; and
   Appendix A shows **no shrinkage step** for (12), printing only "Thus, the
   equation (12) can be derived."

   **Measured** (`src/test_e_update.py` test 4), on the eq. (17) stationarity
   residual `sign(E) + beta_X(E - A)`, whose predicted magnitude is
   `|1 - factor|`:

   | factor | eq. (17) stationarity gap | entries zeroed beyond the eq. (17) radius |
   |---|---|---|
   | **1.0** | **0.000** (exactly optimal) | 0 |
   | **2.0** | **1.000** (unit residual on every surviving entry) | 10-30 per test shape |

   With `factor = 2.0`, entries in the band `1/beta_X < |A| <= 2/beta_X` are
   zeroed that eq. (17) optimality would keep.

   **What we do:** implement `2/beta_X` exactly as eq. (12) prints
   (`E_THRESHOLD_FACTOR = 2.0`), and expose a `factor` parameter so `1.0` is a
   one-line experiment. Calling it a typo in code would substitute our
   expectation for the source — the failure mode this project exists to correct.
   **Resolved by measurement at assembly (g)**; see the carry-forward decision in
   `IMPLEMENTATION_PLAN.md`.

   **Why this belongs in the paper:** it is a concrete, reproducible finding
   about the source method that a careful reimplementer would hit and a casual
   one would not. It also demonstrates the verification discipline the original
   review found lacking.
   *[`src/test_e_update.py` test 4; `src/ssrtd_real.py:update_E`; Appendix A
   eqs (15), (16), (17)]*

12. **THE `beta_X` ERROR MEASURE IS OUR INFERENCE, NOT THE PAPER'S.** eq. (14)
   is printed for `beta_f` only, prefaced *"Take `beta_f` as an example"*, with
   `Err(f^k) = ||f_k - D vec(S_k)||`. The paper states that **both** penalties
   follow the adaptive scheme but **never states the error measure for
   `beta_X`**. We use the natural counterpart — the primal residual of the other
   constraint of eq. (6), `||X - L - S - E||_F`.

   This must not pass as if specified. It is a reasonable reading, it is the
   only obvious candidate, and it is still an assumption we made rather than
   something we read. One methodology sentence.
   *[`src/ssrtd_real.py:primal_residuals`; `src/test_multipliers.py` test 1;
   paper eq. (14) and the sentence introducing it]*

14. 🔴 **ALGORITHM 1'S STOPPING RULE HALTS AFTER ONE ITERATION IF TAKEN
   LITERALLY.** *Rigor finding — the third defect found in the source algorithm.*

   Algorithm 1 stops when `||E_t - E_{t-1}||_F / max{1, ||E_{t-1}||_F} <= 1e-6`.
   `E` is initialized to 0 ("Other variables are initialized by 0"), and **the
   first E-update also returns exactly 0**, because the eq. (12) threshold
   `2/beta_X = 2 * mean(X) / 4e-1 = 5 * mean(X)` exceeds the initial residual
   `|X - L - S|`. The stopping measure is then `0 / max{1, 0} = 0 <= 1e-6`, and
   the loop exits after a single iteration having accomplished nothing.

   **Scale-invariant.** `beta_X` is defined as `4e-1/mean(X)`, so the threshold
   scales with the data and the degeneracy survives any normalization — it is not
   an artifact of our `[0,1]` frames. Observed identically on clean and
   10%-impulse-noise synthetic inputs.

   **The algorithm is fine; the criterion is the defect.** `beta_X` grows under
   eq. (14), the threshold shrinks, and `E` becomes nonzero after a few
   iterations, after which the measure is meaningful. Confirmed by running past
   it: `err_X` fell 7.63 -> 0.53 over 60 iterations while `beta_X` rose
   0.72 -> 27.4 on exactly the stalled iterations.

   **What we do:** the relative change of an identically-zero sequence carries no
   information, so the convergence test is **skipped while `||E_{t-1}||_F = 0`**.
   If `E` never becomes nonzero the loop runs to `max_iter` and reports
   `converged = False`. One rule, minimal, documented in the code as ambiguity 3.

   **Any faithful reimplementation hits this on the first run.** One methodology
   sentence, and a strong illustration of why the verification discipline
   mattered.
   *[`src/ssrtd_real.py:ssrtd_real` ambiguity 3; `src/test_ssrtd_real.py` test 3
   (c)]*

15. 🔴 **THE PRINTED PSNR FORMULA OMITS THE DIVISION BY PIXEL COUNT.**
   *Rigor finding — the fourth internal inconsistency found in the source paper.*

   §IV defines, as printed (verified against the rendered page):
   `PSNR = 10 * log10( 255^2 / ||I - I_hat||_F^2 )`, with `I` and `I_hat` the
   original and recovered background, averaged over all frames. The squared
   Frobenius norm **sums** the error over every pixel and is never divided by the
   pixel count, so this is not the standard per-pixel-averaged PSNR.

   **The reported numbers only fit the standard definition.** For a `288 x 352`
   frame, the literal formula sits `10 * log10(101,376) ≈ 50 dB` below standard
   PSNR. Table I reports SS-RTD at **43.27 dB** on Candela with 10% noise:
   - under the *literal* formula that requires a **total** squared error of about
     3 grey levels² across the entire frame — implausibly small for denoised video;
   - under the *standard* formula it corresponds to a **mean** squared error of
     about 3.1 grey levels² (RMSE ≈ 1.75) — entirely plausible.

   So Table I was almost certainly computed with standard PSNR, and the printed
   definition dropped the `1/(HW)`. This rests on the magnitude of the reported
   numbers, not on anything the paper states.

   **What we do:** standard PSNR, `10 * log10(255^2 / MSE)` with MSE the mean over
   pixels, computed per frame against the ground-truth background and averaged over
   frames, as the paper describes. Any comparison against Table I uses this
   definition. One methodology sentence.
   *[paper §IV, "Performance evaluation indices"; Table I; `src/gate_candela.py`]*

   **Running tally of source-paper inconsistencies** (for the rigor paragraph):
   item 1 (rank rule infeasible for non-square frames), item 11 (E-threshold
   `2/beta_X` vs Appendix A's `1/beta_X`), item 14 (stopping rule halts after one
   iteration), item 15 (PSNR formula). Plus disclosed inferences where the paper is
   silent: item 12 (`beta_X` error measure). Candidate fifth finding, an inference not
   yet confirmed: item 17 (SSIM convention).

17. 🔶 **LIKELY SSIM CONVENTION MISMATCH — CANDIDATE FIFTH FINDING.**
   *Inference from numerical closeness, NOT confirmed.*

   Table I reports SS-RTD SSIM **0.9019** on Candela at 10% noise. The gate result gives
   **0.9939** (factor 1.0) / **0.9937** (factor 2.0) with SSIM computed correctly for
   0-255 images (Wang et al. 2004 settings, `data_range = 255`). That is *higher* than
   the paper, even though our PSNR is slightly *lower* (42.83 vs 43.27 dB). At around
   43 dB an SSIM near 0.99 is the expected value, so 0.90 points to a different SSIM
   computation rather than a worse reconstruction.

   **Most likely cause:** MATLAB's `ssim` takes its default dynamic range from the image
   class, which is 1 for `double`. Passing 0-255 images stored as `double` without setting
   the range shrinks SSIM's stabilizing constants by a factor of 255², which lowers the
   score. Recomputing our saved `L` that way (`data_range = 1`) gives **0.8821**
   (factor 1.0) / **0.8725** (factor 2.0) — **within 0.02-0.03 of the paper's 0.9019**.
   The other conventions tested stay at 0.993-0.994 (scikit-image's default 7x7 window;
   images rounded to uint8).

   **Status: inference.** The paper says nothing about how SSIM was computed beyond
   citing [43], and we have not seen the authors' code. If this goes in the manuscript,
   say "likely" and give the numbers. Our own reported SSIM should use the correct 0-255
   range.
   *[`results/gate_candela/components_factor{1,2}.npz`; RESEARCH_LOG.md §6.5]*

3. **IMPLEMENTATION FAITHFULNESS.** State that we implemented real SS-RTD
   faithfully from Shen et al. 2022 — Tucker/HOOI for `L`, anisotropic TV for
   `S`, L1 for noise `E`, a single `lambda`, and adaptive ADMM penalties — and
   verified each component with unit tests against the paper's equations. This
   is the whole point of the pivot and should be stated as a strength.
   *[paper/SOURCE.md; IMPLEMENTATION_PLAN.md build order]*

---

## For the Experiments / Results section

4. **TIMING — now measured.** One full VIRAT video (`180x320x300`, 100
   iterations, `factor = 1.0`) took **35.9 min** (median 19.8 s/iteration),
   projecting to **~108 h for 180 videos** before H.264 encoding. 16% over the
   Candela-based projection because the machine paged around the memory peak.
   Runs hit the 100-iteration cap rather than the 1e-6 tolerance, on VIRAT as on
   Candela, so the cap is the effective stopping rule and should be reported as
   such. *[RESEARCH_LOG.md §7.1, §7.3]*

5. **OPTIMIZATION DISCLOSURE.** Any warm-starting or float32 optimization adopted
   must be reported as a documented deviation with a before/after comparison —
   not silently absorbed. The `rfftn`/`irfftn` solve adopted 2026-09-19 is **not**
   a numerical deviation: it is mathematically identical to the full-spectrum
   solve and was verified so at 1e-12 (`src/test_s_update.py` test 3). One clause
   in the implementation description suffices.
   *[IMPLEMENTATION_PLAN.md (g) carry-forward decisions]*

---

## For the Limitations section

6. **MEMORY — now measured.** 7.8 GB RAM machine. Full-loop peak working set
   **3,512 MB** per video at full resolution, float64, after the half-spectrum
   FFT change — float32 was **not** needed, so precision is unchanged at float64.
   The machine still paged around the peak (commit charge 93%), which is what
   drove the timing overrun; two allocation levers follow. Report float64 and the
   `180x320x300` working resolution as the conditions.
   *[RESEARCH_LOG.md §7.1, §7.2]*

---

## Verification record (for reproducibility claims / rebuttal to reviewers)

7. **Every component built was unit-tested against the paper's equations at
   machine epsilon.** This directly answers the original review's rigor
   concerns.

   | Component | Tests | Headline numbers |
   |---|---|---|
   | (a) TV operators — eq. (4), (9) | 20/20 | adjoint identity **1.3e-16**; Phi-vs-direct **5.2e-16** |
   | (b) Tucker/HOOI — eq. (3), (8) | 22/22 | exact recovery **4.6e-16**; monotone decrease; orthogonality **2.4e-15** |
   | (c) S-update — eq. (9) | 21/21 | linear residual **2.6e-16**; DC guard confirmed |

   All three suites are re-run as regressions on every subsequent component.
   Reproduce with `python -m src.test_tv_operators`, `python -m src.test_hooi`,
   `python -m src.test_s_update`.

16. ✅ **THE IMPLEMENTATION REPRODUCES THE PAPER'S OWN FIG. 3 ON THE PAPER'S OWN DATA.**
   *A strong rigor point for the methodology section.*

   Beyond the component unit tests (162 assertions across seven suites), the fully
   assembled SS-RTD was run against the paper's convergence experiment: SBI Candela,
   first 80 frames, 10% random-valued impulse noise, lambda 0.4, 100 iterations. **It
   passed every paper-derived criterion for both E-threshold factors:**
   - final relErr_L **0.0137** (factor 1.0) against the paper's ~0.013;
   - relChg_L starting at **0 (1.5e-15)**, as Fig. 3 shows;
   - relChg_L and relChg_S decaying to about 0;
   - average gap from 39 digitized Fig. 3 points **0.0030** (factor 1.0).

   **relErr_L at iteration 1 matched to three decimals — 0.0628 against 0.0626** — which
   also confirms the input frames are the paper's. Standard PSNR came within 0.44 dB of
   Table I (42.83 vs 43.27).

   This is what lets the paper say its SS-RTD results are results of SS-RTD — the property
   the original manuscript lacked. The same run settled item 11 by measurement: factor 1.0
   (Appendix A's value) fits the paper's figure better, and is the factor used for VIRAT.
   Report the one unexplained discrepancy alongside it — relChg_L at about 5x the paper's
   value in iterations 15-40, decaying by the end — rather than leaving it out.
   *[RESEARCH_LOG.md §6; IMPLEMENTATION_PLAN.md (g2); `src/gate_candela.py`;
   `results/gate_candela/summary.json`]*

---

## Candidates for the Discussion section

> Added during the build; not in the original dictation. These are findings that
> do not fit the categories above but would weaken the paper if omitted.

8. **The DC-bin dependency is worth one sentence.** `D*D` annihilates constants,
   so `Phi` has a zero eigenvalue and the eq. (9) denominator
   `beta_X * 1 + beta_f * Phi` reduces to exactly `beta_X` at the DC bin. The
   identity term is therefore the only thing that keeps the solve well posed
   there — a detail the paper does not remark on, and one any reimplementer
   would need. Confirmed numerically: `Phi.min() = 0.0` and
   `denom.min() == beta_X` on every shape tested.
   *[`src/test_s_update.py` test 2; IMPLEMENTATION_PLAN.md (a) carry-forward]*

13. **THE TWO PENALTY SCHEDULES DIFFER IN KIND, NOT DEGREE — AND THAT MAY
   EXPLAIN THE BASELINE'S COLLAPSE.** Real SS-RTD's eq. (14) grows `beta`
   **conditionally** (only when the residual fails to shrink by `c2 = 0.95`)
   and **without any cap**. The old baseline ramped `mu` **unconditionally**
   every iteration and capped it at `1e6` (`src/ssrtd.py:75,90`:
   `mu = min(mu * 1.5, 1e6)`).

   | | Real SS-RTD, eq. (14) | Naive baseline, `ssrtd.py` |
   |---|---|---|
   | Trigger | only on stalled residual | every iteration, unconditionally |
   | Factor | `c1 = 1.15` | `1.5` |
   | Cap | none | `1e6` |
   | 100-iteration bound | `1.174e6` (worst case, never converging) | saturates after ~40 iterations regardless |

   **Consequence for the baseline:** because `mu` saturated at `1e6` after ~40
   of 500 iterations, the effective soft-threshold radii `lam_s/mu` and
   `lam_n/mu` fell to ~`1e-8` — below the `1e-6` near-zero threshold
   `metrics.compute_sparsity` itself uses. **The tuned lambdas may therefore
   have been inert for the large majority of each run**, which is an independent
   candidate mechanism for the winner-takes-all collapse, separate from the
   two-L1 argument. The real algorithm's penalty instead tracks actual
   convergence, so it cannot go inert the same way.

   Currently reasoning plus arithmetic, **not yet measured** — the baseline's
   iteration counts were never recorded (`all_results.csv` has no `n_iter`
   column). **Becomes answerable when (g) logs `beta` per iteration on real
   data.** See `RESEARCH_LOG.md` §4 item 1.
   *[`src/test_multipliers.py` test 5; `src/ssrtd.py:75,90`; RESEARCH_LOG.md §4
   item 1]*

18. 🔶 **FIRST LOOK: ON CLEAN SURVEILLANCE VIDEO, `S` AND `E` SHARE THE SHARP
   EDGES.** *One video, one lambda. A first look, NOT a result — Phase 3 decides.*

   Real SS-RTD on VIRAT `video_01` (`lambda = 0.4`, `factor = 1.0`, 100
   iterations): `L` is a clean background; but `E`, with no injected noise to
   absorb, lands on the sharp structural edges of the *background* (umbrella rims,
   stair treads, railings), and `S` — meant to be the TV-smooth foreground —
   carries the same edge structure plus a broad ±0.02 field, with the walking
   people visible only as small blobs. **45% of pixels where `|S| > 0.05` also
   have `|E| > 0.05`**: the components share edges rather than separate.

   If it holds across videos and across `lambda` in [0.2, 1], this is the
   smooth-vs-sharp finding the pivot exists to test. Until then the caveats are
   the result: single video; single `lambda`; clean input so `E` has no designated
   job (the noise-injection question in `RESEARCH_LOG.md` §7.4); no ground truth.
   *[RESEARCH_LOG.md §7.4; `results/scratch/measure_virat_one/`]*

9. **The baseline retains its value under the new framing.** The collapse
   finding, the parameter-ratio mechanism and the hybrid negative result are all
   real properties of the naive three-component method and survive relabeling.
   Only the attribution to SS-RTD was wrong. Worth stating plainly rather than
   burying, since it is what makes the pivot a reframing rather than a
   retraction.
   *[ARCHIVE_BASELINE.md §4; RESEARCH_LOG.md §4 item 1]*
