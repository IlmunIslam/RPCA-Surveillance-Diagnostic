# PAPER NOTES — findings from the Phase 1 build that must reach the manuscript

> Running record. Every finding from the implementation that changes what the
> paper must say, filed under the section it informs, so nothing discovered
> during the build is lost before Phase 5 writing.
>
> **Append to this file as (d), (e), (f), (g) are built.** Each entry should
> carry its source — the log entry, plan section or test that establishes it —
> so a claim in the manuscript can be traced back to something verified.
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

3. **IMPLEMENTATION FAITHFULNESS.** State that we implemented real SS-RTD
   faithfully from Shen et al. 2022 — Tucker/HOOI for `L`, anisotropic TV for
   `S`, L1 for noise `E`, a single `lambda`, and adaptive ADMM penalties — and
   verified each component with unit tests against the paper's equations. This
   is the whole point of the pivot and should be stated as a strength.
   *[paper/SOURCE.md; IMPLEMENTATION_PLAN.md build order]*

---

## For the Experiments / Results section

4. **TIMING.** Real SS-RTD at literal settings is **~90-95 h for 180 videos**
   single-threaded (HOOI ~62 h, plus roughly a third again for the FFT solve).
   Report actual runtime once measured with the full loop.
   *[IMPLEMENTATION_PLAN.md (b) timing decision and (c) status block]*

5. **OPTIMIZATION DISCLOSURE.** Any warm-starting or float32/rfftn optimization
   adopted at (g) must be reported as a documented deviation with a
   before/after comparison — not silently absorbed.
   *[IMPLEMENTATION_PLAN.md (b), (c) carry-forward items]*

---

## For the Limitations section

6. **MEMORY.** 8 GB RAM machine; peak **~2.84 GB for the S-update alone** at
   full resolution (`180x320x300`, float64). May force float32 (precision cost:
   float32 reaches ~1e-7 against the paper's 1e-6 stopping criterion) or
   `rfftn`. Report the final precision and resolution used, and their
   implications.
   *[IMPLEMENTATION_PLAN.md (c) status block; `src/test_s_update.py` probe]*

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

9. **The baseline retains its value under the new framing.** The collapse
   finding, the parameter-ratio mechanism and the hybrid negative result are all
   real properties of the naive three-component method and survive relabeling.
   Only the attribution to SS-RTD was wrong. Worth stating plainly rather than
   burying, since it is what makes the pivot a reframing rather than a
   retraction.
   *[ARCHIVE_BASELINE.md §4; RESEARCH_LOG.md §4 item 1]*
