# IMPLEMENTATION PLAN — Real SS-RTD (Phase 1)

## Ground rules

- Source of truth: `paper/SOURCE.md` (verified equations) and the gitignored PDF on disk.
- Build each component in isolation, unit-test it, THEN assemble. Nothing is trusted until
  tested.
- New file: `src/ssrtd_real.py` (do NOT overwrite `src/ssrtd.py` yet — keep the old one as the
  documented baseline).
- Single parameter `lambda` in [0.2, 1]. Never two parameters.
- Log per-iteration residual, penalty (`beta`), and convergence from the start (fixes the
  missing-iteration-data problem).

## Output contract (binding on Phase 3 — decided 2026-09-09)

New runs MUST NOT write into the baseline's files or column names. The baseline
results are frozen in `results/baseline_naive/` and backed up off-disk; see
`ARCHIVE_BASELINE.md`.

- **New filenames.** Real SS-RTD writes to `results/metrics/ssrtd_real_results.csv`
  and `results/metrics/ssrtd_real_sweep.csv` — **never** to `all_results.csv` or
  `param_sweep.csv`.
- **Explicit `method` column** in every output row (e.g. `ssrtd_real`,
  `naive_3comp`, `tensor_rpca`), so old and new rows stay distinguishable even if
  they are ever concatenated.
- **Do not reuse the `ssrtd_*` column prefix** for real-SS-RTD quantities. Those
  names belong to the baseline's history. Real SS-RTD's components are `L`, `S`
  (TV-smooth foreground) and `E` (sparse noise) — name the columns for those, not
  for the baseline's `S`/`N`.
- **Log per-iteration state** (`relChg` of `L`, `S`, `E`; `relErr` of `L`; both
  penalties; iteration index) to a per-run file. Figures 3 and 4 of the Phase 5
  plan and the unresolved `mu`-saturation question in `RESEARCH_LOG.md` §4 item 1
  all depend on this existing.

**Why this is a rule and not a preference:** `run_pipeline.py:206-209` and
`param_sweep.py:110-111` both **append** — there is no dedupe on `video_id`. A
Phase 3 run pointed at the old filenames would interleave new rows among the 180
baseline rows under identical column names, with nothing in the data to separate
them, and the contamination would be silent.

## Build order (each is a checkpoint — verify before moving on)

### (a) TV difference operators + Phi precompute — eq (4), (9) ✅ DONE 2026-09-09

- Implement `Dh`, `Dv`, `Dt`: forward differences along height, width, time, with PERIODIC
  boundary conditions (paper states periodic).
- Implement the adjoint `D*` (needed for eq 9).
- Precompute `Phi = |fftn(Dh)|^2 + |fftn(Dv)|^2 + |fftn(Dt)|^2` (computed once).
- UNIT TEST: verify `D*` is the true adjoint of `D` (inner-product test:
  `<D x, y> == <x, D* y>` within numerical tolerance). Verify `Phi` matches applying the
  operators directly on a small random tensor.

**Status: verified 2026-09-09.** Built in `src/ssrtd_real.py` (`tv_forward`,
`tv_adjoint`, `tv_norm`, `compute_phi`); tests in `src/test_tv_operators.py`,
run with `python -m src.test_tv_operators`. 20/20 assertions pass across four
tests — the two required by this plan plus a constant-maps-to-zero check
(catches non-periodic edges) and a hand-checked ramp case (pins difference
direction and axis mapping). Adjoint identity holds to 1.3e-16, `Phi`-vs-direct
to 5.2e-16, i.e. machine epsilon.

> ⚠️ **Carry-forward warning for component (c): `Phi` has a zero eigenvalue.**
> Measured `Phi.min() == 0.0` on every shape tested. This is correct — `D*D`
> annihilates constants, so the DC bin eigenvalue is exactly zero. The eq. (9)
> denominator is `beta_X * 1 + beta_f * Phi`, and **the `beta_X * 1` term is the
> only thing keeping that denominator non-zero at DC**. Dropping it, or writing
> `beta_f * Phi` alone, divides by zero at the DC bin and puts inf/nan into `S`
> on the very first iteration. Keep the identity term explicit, and assert
> `denominator.min() > 0` when (c) is built.

### (b) Tucker / HOOI low-rank solver for L — eq (3), (8) ✅ DONE 2026-09-10

- Ranks `r1 = ceil(0.8H)`, `r2 = ceil(0.8W)`, `r3 = 1`.
- Solve eq (8): `min ||X_tilde - G x1 U1 x2 U2 x3 U3||_F^2` s.t. orthogonal `Uj`, via HOOI
  (paper cites [13]; iterate ~20 inner iterations per the complexity note).
- UNIT TEST: on a synthetic low-rank tensor, HOOI recovers it with small error. Confirm
  `r3 = 1` makes the temporal mode of `L` numerically **rank 1** — i.e. every frame is a
  scalar multiple of one common image (`sigma2/sigma1` ~ 0).
  > **Test wording corrected 2026-09-10.** This bullet originally said "makes every temporal
  > slice of `L` identical", echoing the paper's "each image frame in L is the same". That is
  > not the correct invariant: rank-1 in time gives `frame_t = u3[t] * (common image)`, so
  > frames are *proportional*, identical only if `u3` is constant. Measured deviation on
  > synthetic data was 2.8e-2 to 6.3e-2 — asserting literal identity would fail on correct
  > code. See `RESEARCH_LOG.md` §5 item 2.

**Status: verified 2026-09-10.** Built in `src/ssrtd_real.py` (`tucker_ranks`,
`feasible_ranks`, `mode_dot`, `hosvd_init`, `tucker_core`, `tucker_reconstruct`,
`hooi`); tests in `src/test_hooi.py`, run with `python -m src.test_hooi`. 22/22
assertions pass across five tests: exact recovery (to 4.6e-16), rank-1 temporal
mode, monotone objective decrease, factor orthogonality (to 2.4e-15), and the
rank rule. Mode-2 updates use the Gram route; `unfold`/`fold` are imported from
`tensor_rpca` rather than duplicated.

> ⚠️ **The paper's rank rule is infeasible for non-square frames.** `r3 = 1`
> forces `r1 = r2`, so `(144, 256, 1)` is unattainable and we clamp to
> `(144, 144, 1)`. Forced by mathematics, not chosen; needs a methodology
> sentence. Full reasoning in `RESEARCH_LOG.md` §5 item 1.

**Timing decision (2026-09-10): implement the literal paper version; defer
warm-starting until (g) exists.** Measured on one real VIRAT tensor
(`180 x 320 x 300`, ranks `(144, 144, 1)`): HOSVD init 0.72 s, 20 HOOI
iterations 12.33 s (0.62 s/iter), relative error 0.0897. Projected to the full
Phase 3 run at the literal settings — 100 outer x 20 inner, no warm-starting —
that is **~20.5 min per video and ~62 h for 180 videos**, HOOI alone, before the
FFT solve, soft-thresholds and H.264 encoding.

That is an **upper bound**: runs that stop early on the `1e-6` criterion cut it
proportionally, and we do not yet know the real outer-iteration counts. Warm-
starting `U_k` across outer iterations is the obvious lever and would plausibly
cut inner iterations from 20 to 2-5 after the first outer pass (~6-15 h), but it
is a deviation from Algorithm 1. **Decision: build (c)-(g) literally, measure
actual outer-iteration counts on real data, then decide.** If warm-starting is
adopted it goes in `RESEARCH_LOG.md` §5 as a documented deviation with a
before/after comparison, not as a silent optimization.

### (c) S-update via 3D FFT — eq (9) ✅ DONE 2026-09-13

- Build `C = beta_X*(X - L - E) - Lambda_X + ten(D*(beta_f*f - lambda_f))`.
- `S = ifftn( fftn(C) / (beta_X * 1 + beta_f * Phi) )`.
- UNIT TEST: verify the FFT solve satisfies the linear system
  `(beta_X I + beta_f D*D) vec(S) = RHS` to numerical tolerance, by plugging the result back
  in.

**Status: verified 2026-09-13.** Built as `update_S` in `src/ssrtd_real.py`;
tests in `src/test_s_update.py`, run with `python -m src.test_s_update`. 21/21
assertions across five tests: linear-system residual (2.6e-16), DC bin against
the closed form `C/beta_X`, real output, `beta_f = 0` degeneration, and the sign
convention cross-checked against the eq. (8) form of `X_tilde`.

The (a) DC warning is consumed as planned: `update_S` asserts
`denom.min() > 0` and raises with an explanatory message when `beta_X = 0`,
rather than emitting inf/nan. Measured `Phi.min() = 0.0` and
`denom.min() == beta_X` exactly, on every shape.

**Measured on one real VIRAT tensor (`180 x 320 x 300`, float64):**
`compute_phi` 7.77 s once; `update_S` **6.33 s/call**; **peak working set
2,840 MB** against 8 GB of RAM.

> ⚠️ **Two carry-forward items for (g).**
> 1. **Memory.** 2.84 GB is the peak for the S-update *alone*. The full ADMM
>    holds `X, L, S, E, Lambda_X, f, lambda_f` simultaneously plus HOOI factors
>    and FFT temporaries. Levers, in order: `rfftn`/`irfftn` (cuts complex
>    temporaries, no precision cost, but `Phi` must be rebuilt on the
>    half-spectrum and (a) re-tested), then float32 (halves everything, but our
>    tests assert at 1e-12 and float32 reaches ~1e-7, uncomfortably close to the
>    paper's 1e-6 stopping criterion). Measure the real peak at (g) before
>    choosing either.
> 2. **Revised timing.** `update_S` at 6.33 s/call against HOOI's 12.33 s per 20
>    inner iterations makes the FFT solve about a third of the per-outer-iteration
>    cost. The ~62 h figure recorded under (b) covered HOOI only; including (c)
>    the literal-settings estimate is **~90-95 h for 180 videos**.

### (d) f-update (TV auxiliary) — eq (11)

- `f = soft( D vec(S) + lambda_f/beta_f , lambda/beta_f )`,
  `soft(A,tau) = sign(A)*max(|A|-tau,0)`.
- UNIT TEST: soft-threshold correctness on known inputs.

### (e) E-update (sparse noise) — eq (12)

- `E = soft( X - L - S - Lambda_X/beta_X , 2/beta_X )`.
  **[NOTE: threshold is `2/beta_X`, verified from rendered image — NOT `1/beta_X`]**
- UNIT TEST: soft-threshold correctness; confirm the `2/beta_X` threshold is used.

### (f) Multiplier + adaptive penalty updates — eq (13), (14)

- `lambda_f <- lambda_f - gamma*beta_f*(f - D vec(S))`;
  `Lambda_X <- Lambda_X - gamma*beta_X*(X - L - S - E)`. `gamma = 1.1`.
- Adaptive: `beta <- c1*beta` ONLY IF `Err(f^{k+1}) >= c2*Err(f^k)`, else unchanged.
  `c1 = 1.15`, `c2 = 0.95`. `Err(f^k) = ||f_k - D vec(S_k)||`.
- UNIT TEST: confirm `beta` grows only when residual fails to shrink by `c2`.

### (g) Assemble full ADMM — Algorithm 1

- Init: `L` via `(r1,r2,r3)`-Tucker of `X`; `S = X - L`; `beta_f = 1e+1/mean(X)`;
  `beta_X = 4e-1/mean(X)`; all other vars `0`.
- Loop: update `L` via (8), `S` via (9), `f` via (11), `E` via (12), multipliers+penalties via
  (13), (14).
- Stop: `||E_t - E_{t-1}||_F / max(1, ||E_{t-1}||_F) < 1e-6`, or `iter > 100`.
- Log residual/beta/iter each step.

## VERIFICATION GATE (before ANY VIRAT run)

Reproduce the paper's own behavior on a public benchmark before trusting the implementation:

- Get one dataset the paper used (Candela or Caviar from SBI, or Highway/Office/Pedestrians
  from CDnet).
  > **Verified — use Candela.** The two dataset families serve different tasks in the paper:
  > SBI (Candela, Caviar1, Caviar2) is used for *background subtraction* (PSNR/SSIM, Table I)
  > and is the source of the Fig. 3 convergence curve; CDnet (Highway, Office, Pedestrians) is
  > used for *foreground detection* (F-measure, Table II). Since this gate reproduces Fig. 3,
  > Candela is the exact target. Paper's setup: grayscale 288x352, first 80 frames of the
  > sequence, so the tensor is 288 x 352 x 80. Source:
  > <https://sbmi2015.na.icar.cnr.it/SBIdataset.html>
- Add simulated impulse/salt-and-pepper noise as the paper describes (a ratio of pixels set to
  random values).
  > **Verified — not salt-and-pepper.** The paper's model is *random-valued* impulse noise:
  > "For each image, 10% of pixels are randomly selected to set as random integers in [0, 255],
  > and the positions of the contaminated pixels are unknown." Salt-and-pepper would set pixels
  > to only 0 or 255 and would be a different (easier) corruption. Use 10% of pixels, each
  > replaced by a uniform random integer in [0, 255].
- Run our SS-RTD with `lambda` in [0.2, 1] (paper uses 0.4-0.55).
  > **Verified — use `lambda = 0.4`; "0.4-0.55" is not a range the paper recommends.**
  > `lambda = 0.4` is the single value used for the Candela convergence experiment (§IV-A1),
  > i.e. the value behind Fig. 3 — that is the number this gate should use. `lambda = 0.55`
  > appears only in §V, on the additive-manufacturing X-ray data (384 x 720 x 100), a
  > different domain. For the Table I / Table II benchmark comparisons the paper did not fix
  > `lambda` at all; it tuned by maximin Latin hypercube search over 100 parameter sets. The
  > [0.2, 1] recommendation comes from the Fig. 4 sensitivity sweep (`lambda` varied 0.01 to 3;
  > relative error drops fast below 0.2 and is flat from 0.2 to 3).
- CHECK: convergence curve resembles their Fig. 3 (relative change decreases to ~0).
  Decomposition is sensible: `L` is a clean static background, `S` holds smooth moving
  foreground, `E` holds the noise.
  > **Verified — Fig. 3 specifics.** Fig. 3 plots the relative *change* of `L` and of `S`, and
  > the relative *error* of `L`, over ~100 iterations, where
  > `relChg_A = ||A_k - A_{k-1}||_F / max(1, ||A_{k-1}||_F)` and
  > `relErr_A = ||A_k - A_0||_F / max(1, ||A_0||_F)` with `A_0` the ground truth. No relative
  > error is plotted for `S` because the ground-truth foreground is unknown. So log all three
  > to compare directly. Note the Algorithm 1 *stopping* test uses `E`, while Fig. 3 tracks
  > `L` and `S` — log all of them.
- If we CANNOT roughly reproduce this, the implementation is WRONG. Fix before proceeding.
  Do not run VIRAT until this gate passes.

## Cross-check log (against `paper/SOURCE.md`, performed at write time)

**Every equation reference in this plan matches `paper/SOURCE.md`.** Checked individually:

| Plan step | Equations cited | Verdict |
|---|---|---|
| (a) TV operators + Phi | (4), (9) | ✅ match — anisotropic TV, periodic boundary conditions confirmed |
| (b) Tucker / HOOI | (3), (8) | ✅ match — ranks `(ceil(0.8H), ceil(0.8W), 1)`, HOOI; **20 inner iterations confirmed** from the §III-C complexity analysis ("the HOOI algorithm iterates 20 times") |
| (c) S-update | (9) | ✅ match — `C` expression and the `beta_X*1 + beta_f*Phi` denominator are exact |
| (d) f-update | (11) | ✅ match — threshold `lambda/beta_f`, shift `lambda_f/beta_f` |
| (e) E-update | (12) | ✅ match — threshold `2/beta_X` confirmed against the rendered page image |
| (f) multipliers + penalty | (13), (14) | ✅ match — signs, `gamma=1.1`, `c1=1.15`, `c2=0.95`, `Err` definition |
| (g) Algorithm 1 | Alg. 1 | ✅ match — all initializations and both stopping conditions |

**Three non-equation details did NOT match and are corrected inline above:**

1. **`lambda` = "0.4-0.55"** — not a range from the paper. 0.4 is the Candela convergence
   value; 0.55 is the X-ray AM value from a different section and domain. Use **0.4**.
2. **"salt-and-pepper" noise** — the paper uses random-valued impulse noise (10% of pixels
   replaced by uniform random integers in [0, 255]), not salt-and-pepper.
3. **Dataset choice presented as interchangeable** — SBI and CDnet serve different tasks
   (background subtraction vs. foreground detection). For a Fig. 3 reproduction the dataset
   must be **Candela**.

**Implementation note (naming collision, not a paper mismatch).** The paper uses `lambda` for
the objective weight and `lambda_f` for the TV multiplier vector; these are unrelated
quantities that differ by one character, and both appear in the same expression in eq (11).
`lambda` is also a Python keyword. In `src/ssrtd_real.py` use `lam` for the tuning parameter
and `mult_f` / `mult_X` for the two multipliers, to avoid both the keyword clash and the far
more dangerous `lambda` / `lambda_f` confusion.
