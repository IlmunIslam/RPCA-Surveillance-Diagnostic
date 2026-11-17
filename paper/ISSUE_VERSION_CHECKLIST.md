# Issue-version checklist: what must be re-confirmed against vol. 20, no. 1 (2023)

> **Why this exists.** Everything the project verified "against the paper" was verified
> against the **early-access** PDF (pages 1-14, no volume or issue, `(c)2022`;
> `RESEARCH_LOG.md` §29.2). A reviewer will read the **issue** version (pp. 583-596). IEEE
> copy-edits between the two. This list enumerates what must be confirmed. It does **not**
> predict what changed; nothing here assumes a difference.
>
> **How to use it.** Work through it with both PDFs open. "EA p." is the early-access page.
> For each row, record the issue page and either ✅ **same** or ❌ **differs** with the
> exact new text. Rows marked **R1-R4** carry the four rigor findings; a ❌ there means a
> claim about the source paper is wrong as stated against the version a reviewer reads.
>
> Until every row is ✅, "verified against the paper" in the record means **against the
> early-access version**, and R1-R4 are **provisional** against the issue version.

## 0. Citation and identity

| # | EA p. | confirm in issue version | depends on it |
|---|---|---|---|
| 0.1 | 1 | title, author list and order (Shen, Kamath, Choo, Kong) | the citation |
| 0.2 | — | volume 20, issue 1, **pages 583-596**, year 2023 (the pages have **never** been checked against a source) | the citation, `paper/SOURCE.md` |
| 0.3 | 1 | the DOI printed on the article is 10.1109/TASE.2022.3163674 | the citation |
| 0.4 | 1 | the abstract still says SS-RTD performs well "by taking any λ ∈ [0.2, 1] with anisotropic total variation" | the λ range, item 10 |

## 1. Model and equations (every equation `paper/SOURCE.md` transcribes or the code cites)

Check the **equation number** as well as the content. The code, the tests and the record
cite equations by number, so a renumbering is a ❌ even if the mathematics is unchanged.

| # | EA p. | eq. | what we recorded | depends on it |
|---|---|---|---|---|
| 1.1 | 5 | (3) | `L` is a Tucker decomposition with rank `(r1, r2, r3)` | `ssrtd_real.py`, `test_hooi.py` |
| 1.2 | 5 | (4) | `‖S‖_TV1` is **anisotropic** TV: the l1 norm of stacked horizontal, vertical and temporal differences, **periodic boundary conditions** (text beside (4)) | `test_tv_operators.py`; the FFT S-update |
| 1.3 | 5 | (5) | objective `min ‖E‖_1 + λ‖S‖_TV1` s.t. `X = L + S + E`, `L = G ×1 U1 ×2 U2 ×3 U3` | everything |
| 1.4 | 5 | (6) | the split form with `f = D vec(S)`; its two constraints | item 12 (the `β_X` error measure is inferred from (6)'s second constraint) |
| 1.5 | 5-6 | (7) | augmented Lagrangian with a **negative** inner product `−⟨Λ, ·⟩` | the multiplier sign (`ssrtd_real.py:666`, `test_multipliers.py` test 2) |
| 1.6 | 6 | (8) | HOOI sub-problem for `G`, `Uj` with `Ujᵀ Uj = I` | `test_hooi.py` |
| 1.7 | 6 | (9) | `S` update in closed form via 3D FFT; denominator `β_X·1 + β_f·Φ` | `test_s_update.py`; PAPER_NOTES item 8 (DC bin) |
| 1.8 | 6 | (10) | `f` sub-problem with a **generic `q`** norm | item 10 (anisotropic vs isotropic ambiguity) |
| 1.9 | 6 | (11) | `f` update: soft-threshold at `λ / β_f` | `test_f_update.py`; R2's comparison pattern |
| 1.10 | 6 | (12) | **`E` update: soft-threshold at `2 / β_X`** | **R2** |
| 1.11 | 6 | (13) | multiplier updates; `γ = 1.1` | `test_multipliers.py` |
| 1.12 | 6 | (14) | adaptive penalty `β_f ← c1·β_f if Err(f^{k+1}) ≥ c2·Err(f^k)`, `c1 = 1.15`, `c2 = 0.95`; `Err(f^k) = ‖f_k − D vec(S_k)‖`; introduced by **"Take β_f as an example"**, with no error measure stated for `β_X` | item 12; `test_multipliers.py` |
| 1.13 | 13 | (15), (16), (17) | Appendix A derivations; the **`(β/2)` convention present in all three**; (17) reduces the E-terms to `min ‖E‖_1 + (β_X/2)‖A − E‖²` | **R2** |

## 2. Algorithm 1 (EA p. 6)

| # | line | what we recorded | depends on it |
|---|---|---|---|
| 2.1 | init | **`r1 = ceil(0.8 × H)`, `r2 = ceil(0.8 × W)`, `r3 = 1`** | **R1** |
| 2.2 | init | `L` from the `(r1, r2, r3)`-Tucker of `X`; `S = X − L` | `ssrtd_real.py` init |
| 2.3 | init | `β_f = 1e+1 / mean(X)`, `β_X = 4e−1 / mean(X)` | **R3** (the first-iteration threshold `2/β_X = 5·mean(X)`), init |
| 2.4 | init | **"Other variables are initialized by 0"** (so `E_0 = 0`) | **R3** |
| 2.5 | 1 | **stop rule `‖E_t − E_{t−1}‖_F / max{1, ‖E_{t−1}‖_F} > 10⁻⁶ & iter ≤ 100`** | **R3**; `max_iter = 100` everywhere |
| 2.6 | 2-6 | update order: L (8), S (9), f (11), E (12), multipliers | the solver's loop order |
| 2.7 | 4 | **"Updating f via (11) for anisotropic total variation"** | item 10 |
| 2.8 | 5 | "Updating E via (12)" (still points at the `2/β_X` equation) | **R2** |

## 3. Implementation details and parameter ranges (§III-C, EA p. 6-7)

| # | EA p. | what we recorded | depends on it |
|---|---|---|---|
| 3.1 | 6 | rank text: `r1`, `r2` "set to values of ceil(0.80 × H) and ceil(0.80 × W)" | **R1** |
| 3.2 | 6 | `r3` "takes the value 1 for all experiments so that **each image frame in L is the same**" | item 2 (frame proportionality) |
| 3.3 | 6 | "λ is taken in the range [0.2, 1]" | the single-parameter claim; the λ-sweep arm's range |
| 3.4 | 6 | `γ = 1.1`, `c1 = 1.15`, `c2 = 0.95` (text after (14)) | `ssrtd_real.py` constants |
| 3.5 | 7 | "practitioners can apply the method with any λ ∈ [0.2, 1]" | as 3.3 |
| 3.6 | 7 | the complexity statement ("one outer iteration from line 1 to 7") | only if the manuscript cites the complexity |

## 4. Evaluation definitions (§IV, EA p. 7)

| # | EA p. | what we recorded | depends on it |
|---|---|---|---|
| 4.1 | 7 | **PSNR printed as `10 × log10(255² / ‖I − Î‖_F²)`, no division by pixel count** | **R4** |
| 4.2 | 7 | "Average PSNR and SSIM over all image frames in the video" | R4; `gate_candela.py` averaging |
| 4.3 | 7 | SSIM defined only by citation to [43] (Wang et al. 2004); no convention stated | item 17 (SSIM, candidate) |
| 4.4 | 7 | `relChg_A = ‖A_k − A_{k−1}‖_F / max(1, ‖A_{k−1}‖_F)` and `relErr_A = ‖A_k − A_0‖_F / max(1, ‖A_0‖_F)` | the gate's convergence measures |

## 5. The convergence experiment and Fig. 3 (§IV-A1, EA p. 7-8)

| # | EA p. | what we recorded | depends on it |
|---|---|---|---|
| 5.1 | 7 | Candela (SBI), **first 80 frames**, `288 × 352 × 80` | the gate's input (relErr_L iteration 1 matched 0.0628 vs 0.0626, which also confirmed the frames) |
| 5.2 | 7 | noise: "10% of pixels randomly selected to set as **random integers in [0, 255]**", positions unknown | the gate; the VIRAT noise arm's noise model |
| 5.3 | 8 | λ = 0.4 for the convergence run | the gate; the VIRAT default λ |
| 5.4 | 7 | **Fig. 3**: the curves (`relChg_L`, `relChg_S`, `relErr_L`) and their axes | the gate's D2 overlay |
| 5.5 | 7 | **Fig. 3 values the gate compares against:** `relErr_L` at iteration 1 **0.0626**; final `relErr_L` **~0.0125**; `relChg_L` **starting at 0**; `relChg_L`, `relChg_S` decaying to ~0; the **39 points** we digitized (`src/gate_candela.py:133`, `FIG3_REFERENCE`) | PAPER_NOTES item 16; `RESEARCH_LOG.md` §6. **If Fig. 3 was redrawn, re-digitize and re-run the gate's D2 comparison** |
| 5.6 | 7 | the size of `relChg_L` in iterations 15-40 (ours runs ~5x higher; reported as unexplained) | item 16's disclosed discrepancy |
| 5.7 | 8 | text: "From Fig. 3, the relative change converges to zero" | item 16 |

## 6. Sensitivity, Fig. 4 (EA p. 8)

| # | EA p. | what we recorded | depends on it |
|---|---|---|---|
| 6.1 | 8 | λ swept **0.01 to 3**, same noise as §IV-A1 | `IMPLEMENTATION_PLAN.md` (g2) |
| 6.2 | 8 | **Fig. 4**: `relErr_L ≈ 0.013` at λ = 0.4 | `gate_candela.py:122` `PAPER_RELERR_L = 0.013`; the gate's pass criterion |
| 6.3 | 8 | "drops very fast when 0 < λ < 0.2 and remains very stable when 0.2 ≤ λ < 3"; "λ ∈ [0.2, 1] is recommended" | the λ range |

## 7. Table I (EA p. 9)

| # | what we recorded | depends on it |
|---|---|---|
| 7.1 | SS-RTD, **Candela with 10% noise: PSNR 43.27 dB** | **R4** (the magnitude argument); the gate's 42.83 vs 43.27 comparison |
| 7.2 | SS-RTD, Candela with 10% noise: **SSIM 0.9019** | item 17 (MATLAB `data_range` inference: ours 0.8821 under that convention) |
| 7.3 | the column and row layout: that 43.27 and 0.9019 sit in the SS-RTD row and the Candela-10%-noise column | 7.1, 7.2 |
| 7.4 | (lower priority) Table II (F-measure, EA p. 10) and the datasets in §IV-B (Caviar1/2, 80 frames, `256 × 384`) | cited only in `IMPLEMENTATION_PLAN.md`; no current claim |

## 8. Appendix A (EA p. 13)

| # | what we recorded | depends on it |
|---|---|---|
| 8.1 | the sentence "the steps to obtain (8), (10), and (12)" are given | R2 |
| 8.2 | (15), (16), (17) as in 1.13, with the `(β/2)` factor | **R2** |
| 8.3 | **(16) → (11) carries through to `λ / β_f`** | **R2** (the comparison pattern) |
| 8.4 | **no shrinkage step shown for (12); only "Thus, the equation (12) can be derived."** | **R2** |
| 8.5 | the EA bookmark "Appendix A: Derivations for algorithm ??" is a broken cross-reference; note whether the issue version fixed it (cosmetic) | nothing |

## 9. The four rigor findings: what would invalidate each

| finding | PAPER_NOTES | rows that must all be ✅ | would be wrong as stated if... |
|---|---|---|---|
| **R1** rank rule infeasible for non-square frames | item 1 | 2.1, 3.1, 3.2 | the rule, or `r3 = 1`, is changed in the issue version |
| **R2** eq. (12) prints `2/β_X`; Appendix A implies `1/β_X` | item 11 | 1.10, 1.13, 2.8, 8.2-8.4 | (12) prints `1/β_X`, **or** Appendix A now shows a derivation giving `2/β_X`, or the `(β/2)` convention is gone from (15)-(17) |
| **R3** stop rule halts after one iteration | item 14 | 2.3, 2.4, 2.5, 1.10 | the rule changed (e.g. a minimum iteration count, a different measure or denominator), `E` is no longer initialized to 0, or the `β_X` initialization or (12)'s threshold changed so that the first `E` update is nonzero |
| **R4** PSNR formula omits the pixel count | item 15 | 4.1, 4.2, 7.1, 7.3 | the formula now divides by the pixel count (or uses MSE), or Table I's magnitudes changed |

Also check the **disclosed inferences**, which are claims that the paper is *silent*. A
sentence added in the issue version would make each one wrong:

| item | rows | wrong if... |
|---|---|---|
| item 12 (`β_X` error measure is our inference) | 1.12 | the issue version states `β_X`'s error measure |
| item 10 (eq. (10)'s generic `q` is ambiguous) | 1.8, 2.7 | (10) is made specific |
| item 2 (frames are scalar multiples, not "the same") | 3.2 | the wording changed |
| item 17 (SSIM convention, candidate) | 4.3, 7.2 | the issue version states an SSIM convention or data range |

## 10. After the check

- **All ✅:** record that in `RESEARCH_LOG.md`, and remove the "provisional" notes in
  `paper/SOURCE.md` and `PAPER_NOTES.md` by superseding them, not deleting them.
- **Any ❌:** record the exact difference. A ❌ in R1-R4 changes a claim about the source
  paper, so it goes through the withdrawal rule. A ❌ in an equation the code
  implements means the implementation must be re-verified against the issue text before
  any number built on it is quoted. A ❌ in Fig. 3, Fig. 4 or Table I means the gate's
  comparison values change, so re-run `python -m src.gate_candela` with the new targets.
