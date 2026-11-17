# MANUSCRIPT NUMBERS — the extraction layer for Phase 5

> Material to write from, not prose. Every number the manuscript is expected to carry,
> with its source section in `RESEARCH_LOG.md` (§) unless another file is named, the
> conditions it holds under, and its evidential status. Extracted 2026-11-18 from the
> record as of commit `a7e92df`. **The log is authoritative; if this file and the log
> disagree, the log wins and this file is wrong.**

**Status codes**

| code | meaning | how to write it |
|---|---|---|
| **PR** | pre-registered: definition, prediction and falsification boundary committed before the data were computed | "a pre-registered test showed..." |
| **D** | descriptive: a planned measurement on the full planned sample, not pre-registered | state it plainly, with its spread |
| **X** | exploratory: found after looking at the data | "exploratory", never as support for a claim |
| **W** | withdrawn | never quote; listed so it is recognised |

Defaults unless a row says otherwise: real SS-RTD, `factor = 1.0`, `lambda = 0.4`,
100 iterations (the cap is the effective stopping rule), clean input, first 300 frames,
grey, 320x180. "Threshold" is the measurement cut `|.| > thr` applied to stored
components afterwards. It is **not** the solver's soft-threshold.

---

## A. Sentences that read well and are wrong

Check this before every paragraph. "Live copy" means a current, non-history document
still says it. Those are the places most likely to leak into prose.

| # | plausible sentence | why it is wrong | correct form | live copies still saying it |
|---|---|---|---|---|
| A1 | "...more completely **the emptier the scene**" / "with **scene occupancy**" | `foreground_density` is not an occupancy proxy: ρ +0.382 vs annotated `box_occupancy`, Pearson −0.057 (§25.1) | "...the less **temporal change** the scene contains"; describe the predictor as a median-deviation change detector | 🔴 **`RESEARCH_PLAN.md:16-17`**, missed in the §25 sweep. History-only: §19.1 ("weakens monotonically with scene occupancy"), §10.3 title |
| A2 | "`E` lands on the sharp **background** edges", "the coincidence is **localised to background**", "`S` is penalised out of the **background** edges and `E` takes them over" | the 14.71x inside/outside gap is entirely enrichment's denominator; raw `P(E\|S)` is 31.5% inside boxes vs 29.8% outside (§25.4) | "`S`-membership predicts `E`-membership far above chance" (enrichment); if location is needed, use §25.6 (exploratory): `E`'s **mass** is less foreground-selective than `S`'s | 🔴 **`RESEARCH_LOG.md` §23.1 table row 1** (the canonical claim table); 🔴 `START_HERE.md:72-73`; 🔴 `PAPER_NOTES.md:373`, `:556`; 🔴 `RESEARCH_PLAN.md:79` (Figure 5's spec) |
| A3 | "the sum of `S` and `E` is (nearly) **conserved**" / "a one-for-one handoff" | per video the sum rises 1.257x (0.27–1.56x); 2/20 within ±10% (§20.7a) | "`E` gains about **twice** what `S` loses" | none live. §20.2 is struck through correctly |
| A4 | "a transfer coefficient of ~2" as a characteristic number | τ spread is 0.2–12.5 per video (§20.7a) | the median with its spread, or not at all | none |
| A5 | "`E`'s precision tracks scene emptiness" | ρ −0.764 at n=11 → −0.248 (p≈0.29) at n=20 (§12.2) | precision 0.628–0.996, median 0.925, driver unexplained | none |
| A6 | "the stratified subset enriches more than other videos" / "a selection effect" | 45.7x vs 38.1x (p 0.044, n=54) → 45.7x vs 49.0x, p 0.916, sign reversed (§19.2) | "no selection effect: the effect is larger in the 160 videos selected by nothing" | none |
| A7 | "recall vs density is significant" | ρ −0.791 but recall@0.05 spans 0.8950–0.9047; 0.900 is the threshold's detection ceiling (§12.2) | don't report recall@0.05 as a between-video measure | none |
| A8 | "**47.4x**" with no threshold attached / "a 47-fold effect" | enrichment level moves 10x across a 5x threshold change (§20.7b) | always "at threshold 0.05"; give the 0.01 value beside it | — |
| A9 | "pooled median 47.4x at 0.05, **4.7x at 0.01**" | **4.7x is the 20-video subset at λ 0.4**, not a pooled 180-video value. No 180-video 0.01 headline exists in the record | "47.4x (180 videos, thr 0.05); on the 20-video subset, 40.4x at 0.05 and 4.7x at 0.01" | 🔴 **`RESEARCH_LOG.md` §23.1 table row 1** mislabels it |
| A10 | "enrichment is the **robust / stable** statistic" | robust to `factor`, noise condition and λ; **fragile to the measurement threshold** (§20.7b). Enrichment itself moves 2.12x under λ (§20.5) | state the scope; the threshold-robust quantity is enrichment's **λ-slope** | none |
| A11 | "the sink is **proved** / the mechanism is **established**" by §22 | §22 refutes one rival (idleness); it does not prove the mechanism, and was powered against *abolished*, not *slightly damped* (§22.4) | "a pre-registered test refuted the idleness explanation" + CI [1.151, 1.387] | — |
| A12 | "the noise slope equals the clean slope (0.3% apart)" | the 0.3% agreement is not evidence of equality (§22.4) | quote the CI | — |
| A13 | "noise increases enrichment by 3–8%" | flagged, not claimed; within the β_X confound (§22.3) | don't mention it, or mention it as unexplained | — |
| A14 | "on noisy input the transfer should be weaker" | §20.6's prediction; refuted by §22 | — | history only |
| A15 | "the asymmetry shrinks under noise" / "§27 confirms the misfit sink" | §25.6's direction was idleness's prediction (§26.1). PRESERVED is weak evidence, the same verdict a null produces (§26.7, §27.1) | "`E`'s spatial distribution is preserved under noise (pre-registered; weak by design)" | 🔴 `PAPER_NOTES.md:523` still says the test is "not yet run" |
| A16 | "`E` is ~19x less foreground-selective than `S`" as a finding | exploratory; its existence cannot be confirmed on this data (§26.1(3)); threshold-sensitive (>1 on only 15/20 noise-subset videos at 0.01) | exploratory, if at all | — |
| A17 | "the dose-response is ρ −0.731 / slope −0.54" | the 20-video subset; superseded by 180 videos (§19.1) | ρ −0.508, slopes −0.517 / −0.537 | 🔴 `PAPER_NOTES.md:31` (framing section) |
| A18 | "**the** untested alternative is enrichment inside vs outside the boxes" | tested in §25.4, not supported | — | 🔴 `PAPER_NOTES.md:532-533`, `:597-598`; §22.4 (history) |
| A19 | "`S` and `E` share the sharp **edges**" as a measured fact | "edges" is a visual reading of one video (§7.4). The measurement is support co-occurrence (enrichment), never an edge measure | "the supports of `S` and `E` coincide far above chance"; "edges" only when describing a figure | `PAPER_NOTES.md:365` heading, `START_HERE.md:72` |
| A20 | "the claim holds for **any** `L+S+E` decomposition" as shown | argued from the update's form (elementwise L1 with no designated signal); measured on **one** instrument, SS-RTD. The naive baseline was not tested for it | "we argue it applies to the model class; we measure it on SS-RTD" | §23.1 closing paragraph (as argument, fine) |
| A21 | "trajectories are bitwise reproducible" | bitwise within one machine and FFT path; across FFT/BLAS builds only to reported precision (§6.6) | — | — |
| A22 | "162 assertions" | was true at the gate; now **248** across seven suites (§7.5) | 248 | 🔴 `PAPER_NOTES.md:298` |
| A23 | "300/300 runs" | Phase 3 closed at **320/320**, six arms (§22.5) | 320 | 🔴 `PAPER_NOTES.md:366` |
| A24 | "on Candela, `E` holds the noise" (Figure 5's premise) | on the gate run only **13.4%** of `E`'s nonzeros are real noise at factor 1.0 (74.6% of pixels nonzero vs 10% corrupted) (§6.1) | see Figure 5 below | `RESEARCH_PLAN.md:77-79` |

---

## B. Methodology: the source paper and the implementation

| id | value | source | conditions | status |
|---|---|---|---|---|
| B1 | rank rule infeasible for non-square frames; VIRAT uses `(144,144,1)` not `(144,256,1)` | §5 item 1; PAPER_NOTES 1 | `r3 = 1` forces `r1 = r2` | D |
| B2 | `L`'s frames are scalar multiples of one image; frame deviation 2.8e-2 to 6.3e-2 | §5 item 2; PAPER_NOTES 2 | test_hooi test 2 | D |
| B3 | anisotropic vs isotropic TV differ by max 0.7999 on a test case | PAPER_NOTES 10 | test_f_update test 4 | D |
| B4 | eq. (12) prints `2/β_X`; Appendix A implies `1/β_X`. Stationarity gap 0.000 (factor 1) vs 1.000 (factor 2) | PAPER_NOTES 11 | test_e_update test 4 | D |
| B5 | β_X error measure is our inference (`‖X−L−S−E‖_F`), not stated in the paper | PAPER_NOTES 12 | — | disclosed assumption |
| B6 | Algorithm 1's stop rule halts after 1 iteration if literal; err_X 7.63 → 0.53 over 60 iterations once skipped | PAPER_NOTES 14 | synthetic | D |
| B7 | printed PSNR omits ÷pixel count: ~50 dB offset for 288x352; literal formula gives −7.2 / −7.4 dB on our result | PAPER_NOTES 15; §6.5 | — | D |
| B8 | SSIM likely MATLAB default range: our 0.9939 → 0.8821 with `data_range=1`, vs paper 0.9019 | PAPER_NOTES 17; §6.5 | factor 1 (0.8725 at factor 2) | **inference, say "likely"** |
| B9 | unit tests: **248 assertions, seven suites**; adjoint 1.3e-16, Φ 5.2e-16, Tucker recovery 4.6e-16, orthogonality 2.4e-15, S residual 2.6e-16 | §7.5; PAPER_NOTES 7 | — | D |
| B10 | Candela gate: relErr_L final **0.0137** (paper ~0.013); iteration 1 **0.0628 vs 0.0626**; Fig. 3 gap **0.0030** over 39 digitised points; PSNR **42.83 vs 43.27 dB** | §6, §6.1, §6.2 | SBI Candela frames 85-164, 10% impulse, seed 0, λ 0.4, factor 1 | D |
| B11 | factor 2 on the gate: Fig. 3 gap 0.0040, PSNR 42.66, err_X 280.5 vs 79.7 | §6.1 | as B10 | D |
| B12 | relChg_L plateau ≈0.010 over iterations 15–40 vs paper ≈0.002 (~5x); explained on our side, cause of the gap not determinable | §6.3 | both factors | D, **report it** |
| B13 | half-spectrum S-update: ~3e-16 relative per call; ADMM amplifies it (err_X 3.5e-2 apart by iteration 100); gate passes on both paths | §6.6 | — | D |
| B14 | FFT-path robustness on `video_01`: L/S/E differ 1.9e-3 / 3.1e-3 / 3.1e-2; S∩E share 12.672% vs 12.673%; 2.5% of E-claimed voxels flip at 0.05 but the aggregates hold | §7.8; PAPER_NOTES 18 | thr 0.05 | D |
| B15 | memory: peak **2,663 MB**, float64, levers A–E each bitwise vs reference (3,512 → 3,187 → 2,663 MB) | §7.5–§7.7 | full resolution | D |
| B16 | runtime: ~22 min/video (12.3 s/iter) standalone; batch 24.4–28.5 min/run, median 25.2 | §7.7; §10 | 7.8 GB machine | D |
| B17 | every run hit the 100-iteration cap, never tol 1e-6 | §10; PAPER_NOTES 4 | — | D |
| B18 | within one machine and FFT path the pipeline is deterministic: batch `video_01` identical on 14 statistics to the smoke run | §10 | — | D |

---

## C. The main finding: `S` and `E` supports coincide (enrichment)

`enrichment = P(E-claimed | S-claimed) / P(E-claimed)`; 1.0 = independent.

| id | value | source | conditions | status |
|---|---|---|---|---|
| C1 | enrichment > 1 on **180/180** videos | §19.1 | thr 0.05 | D |
| C2 | pooled median **47.4x**, range **2.4–453.3x** | §19.1 | **thr 0.05**, 180 videos | D |
| C3 | subset 20: median **40.4x** (2.4–199.8x); rest 160: **49.0x** (12.0–453.3x) | §10.1, §19.1 | thr 0.05 | D |
| C4 | threshold dependence, subset 20: **4.7x at 0.01 vs 40.4x at 0.05**; raw P(E\|S) 36.2% vs 31.3%; P(E) 7.47% → 0.80% | §20.7b | λ 0.4, 20 videos | D |
| C5 | 2x2 odds ratio median **94x** (3.7–364x) | §10.1 | subset 20, thr 0.05 | D |
| C6 | don't quote the pooled ratio (4.9x): `video_01` carries 90% of the expected count | §10.1 | — | — |
| C7 | `video_01` is the weakest of 20 (**2.4x**); fg 4.263% vs subset median 0.403% | §10.2 | — | D, label the figure video as conservative |
| C8 | `video_01` whole tensor: `|S|>.05` 16.98%, `|E|>.05` 5.25%, P(E\|S) 12.67%; per-frame overlap 2.2–54.3% (median 24.7%); figure frame 48.6% | PAPER_NOTES 18 | thr 0.05 | D, one video |
| C9 | factor 2.0: median **21.9x**, 20/20 > 1, rank ρ +0.847 vs factor 1; err_X ~2x larger | §14.1 | subset 20 | D (robustness table) |
| C10 | raw share 2.16x more `factor`-sensitive than enrichment (79.5% vs 36.8% median abs change) | §14.2 | subset 20 | D (Methods sentence, not a contribution) |

---

## D. Dose-response (temporal change)

| id | value | source | conditions | status |
|---|---|---|---|---|
| D1 | enrichment vs `foreground_density`: ρ **−0.508** (p≈3.3e-13) | §19.1 | 180, thr 0.05 | D |
| D2 | log-log slope **−0.517** (rest 160) vs **−0.537** (subset 20) | §19.1 | thr 0.05 | D, the cross-group agreement |
| D3 | vs `foreground_density` at thr 0.01: ρ −0.509 (p 3.1e-13) | §25.2 | 180 | D |
| D4 | partial controlling `S_claimed_px` ρ −0.529; support-size term reverses sign to +0.357 | §10.3 | **subset 20 only** | D, n=20 |
| D5 | holds at all five λ, strengthening ρ −0.564 → −0.801 | §20.1, §20.4 | subset 20 | D |
| D6 | **proxy validation fails**: ρ(`box_occupancy`, `foreground_density`) **+0.382**, Pearson **−0.057** vs a pre-set bar of ρ ≥ +0.70 | §25.1 | 180 | **PR** (pre-specified §24) |
| D7 | **dose-response survives vs annotated occupancy**: ρ **−0.329** (p 6.4e-06) thr 0.05; **−0.234** (p 1.6e-03) thr 0.01 | §25.2 | 180 | **PR** (pre-specified §24) |
| D8 | `video_101`: fg 0.0237% (4th lowest), occupancy 10.197% (rank 138/180), enrichment 135x: parked cars belong in `L` | §25.3a | thr 0.05 | D, illustrative |
| D9 | only 12 of the 20 lowest-fg videos are among the 20 lowest-occupancy | §25.3a | — | D |
| D10 | `video_173` breaks the trend (fg 0.174%, 175x; `E` support unusually small) | §10.3 | — | D, look before quoting |

---

## E. λ: the model's only parameter

| id | value | source | conditions | status |
|---|---|---|---|---|
| E1 | medians **29.4 / 40.4 / 47.3 / 49.2 / 55.0x** at λ 0.2 / 0.4 / 0.6 / 0.8 / 1.0 | §20.1 | subset 20, thr 0.05 | D |
| E2 | > 1 in **96/96** defined runs | §20.1 | — | D |
| E3 | paired vs λ 0.4: **0.83 / 1.14 / 1.22 / 1.29x**; 16/17 move up at each point above 0.4 | §20.3 | 17-video balanced panel | D, quote paired |
| E4 | `S` claimed voxels 154,667 → 25,231 (**6.1x fewer**); `E>.05%` 0.447 → 1.232 (**2.8x more**), λ 0.2 → 1.0 | §20.2 | 17-video panel | D |
| E5 | sum `S+E` rises **1.257x** per video (0.27–1.56x); τ median 1.8–2.7, spread 0.2–12.5 | §20.7a | 20 | D (this replaces the withdrawn "conserved") |
| E6 | annihilation (`S_claimed_px = 0`): `video_104` at 0.8; `video_104`, `video_54`, `video_26` at 1.0. Undefined, never imputed | §20.3 | thr 0.05 | D |
| E7 | λ 0.4 (Shen et al.'s value) is near the conservative end | §20.2 | — | D |
| E8 | rank ρ vs λ-0.4 ordering +0.932 / +0.991 / +0.972 / +0.968 | §20.4 | — | D |
| E9 | raw share 4.28x more λ-sensitive than enrichment (9.08x vs 2.12x) | §20.5 | 17 | D, a reporting choice, not a finding |
| E10 | λ-slope is threshold-robust: 1.240x (0.01) vs 1.290x (0.05) | §20.7b | 20 | D |

---

## F. Noise condition and the idleness rival

| id | value | source | conditions | status |
|---|---|---|---|---|
| F1 | `video_01`: enrichment 2.42x clean, **2.31x** uncorrupted voxels under noise, **0.99x** corrupted voxels | PAPER_NOTES 18; §9.4 | 10% impulse, seed 0, thr 0.05 | D, one video |
| F2 | noise-subset uncorrupted: median **41.9x** (2.31–208.9x) vs clean 40.4x; rank ρ **+0.994**; vs fg ρ −0.738 | §12.1 | 20, thr 0.05 | D |
| F3 | **§22 primary**: paired λ 0.4→1.0 ratio, noise (uncorrupted) **1.263x**, CI **1.151–1.387**, 17/20, p 2.58e-03; clean 1.267x, CI 1.141–1.407, 17/20 | §22.1 | thr 0.01, 20 | **PR** (§21, `63913fb`): H1 held, idleness refuted |
| F4 | registered bar ≥1.15x and ≥16/20; falsified at ≤14/20 or <1.10x | §21.4 | — | PR |
| F5 | secondary thr 0.05: clean 1.424x (16/17), noise 1.397x (15/16) | §22.1 | — | PR (non-deciding) |
| F6 | corrupted-voxel enrichment **0.987x** (λ 0.4) / **0.994x** (λ 1.0) | §22.2 | thr 0.01 | PR control |
| F7 | β_X noise/clean **0.652x** (λ 0.4), 0.745x (λ 1.0): `E`'s threshold ~1.53x / 1.34x higher under noise | §21.2, §22.2 | — | D (the confound) |
| F8 | reconstruction under noise: median gain **+20.35 dB** (13.02–28.38), SSIM median 0.988; `video_01` weakest at +13.02 dB (31.71 vs 18.68 dB) | §12.1; §9.3 | PSNR L+S vs clean | D |
| F9 | `E` recall@0.05 ≈0.900 is a detection ceiling (~10% of impulses redrawn too close to the original) | §12.2 | — | D, don't use as a between-video measure |
| F10 | `E` precision@0.05 0.628–0.996, median 0.925, driver unexplained | §12.2 | 20 | D |

---

## G. Annotation-based tests (§24–§27)

| id | value | source | conditions | status |
|---|---|---|---|---|
| G1 | annotation coverage: 180/180 matched, ≥251 annotation rows in frames 0–299, 0 out-of-bounds boxes | §24.1 | — | D |
| G2 | `box_occupancy` median **1.490%** (0.111–25.849%) | §25.1 | all object types | D |
| G3 | **§24.4 not supported**: enrichment outside/inside **14.71x** (157/179) at 0.05, 2.33x at 0.01, entirely the denominator. Raw P(E\|S) **31.5% inside vs 29.8% outside**; `E` 17.60x denser inside | §25.4 | — | **PR, NOT SUPPORTED** |
| G4 | E:S density **5.586** background vs **0.568** inside; asymmetry 10.22x median, 166/179, p 5.6e-35; `S` 306x vs `E` 16x foreground-concentrated | §25.6 | thr 0.05 | **X** |
| G5 | asymmetry vs occupancy ρ −0.618 / −0.699: **partly circular, not support** | §25.6 | — | X, never quote as evidence |
| G6 | `E`-selectivity under noise: adjusted ratio **1.061**, CI **0.988–1.138**; unadjusted 0.955 (0.926–0.985), already inside the band; 18/20 in band; **PRESERVED** | §27 | thr 0.01, uncorrupted voxels, 20 | **PR (`3b59daf`), weak by design**: also what a null produces |
| G7 | λ 0.4→0.6 moves the E:S asymmetry 1.765x but `E`'s own selectivity only 0.85–1.07: the volatility is `S`'s | §26.1 | 20 | D |

---

## H. Figures

RESEARCH_PLAN lists **six** figures, not five: 1 pipeline, 2 decomposition, 3
convergence, 4 λ sensitivity, 5 misfit sink, 6 baseline comparison. Plus three tables.

| fig | numbers it needs | in the record? | flags before designing it |
|---|---|---|---|
| **1 Pipeline** | none | n/a | update the labels for the framing; `S` = sparse **moving** term |
| **2 Decomposition** | C7, C8 (frame 151, `video_01`) | yes | `video_01` is the **weakest** of 20 (2.4x); the caption must say it's conservative and quote the whole-tensor numbers, not the frame's (48.6% vs whole-tensor 12.67%). RESEARCH_PLAN calls `S` "smooth foreground" (it isn't, §7.4). Caption wording risk A2/A19. Consider adding a typical-enrichment video beside it |
| **3 Convergence** | relChg_L/S, err_X, β per iteration on VIRAT; B12, B17 | histories exist per run (`history.csv`); **no summary of VIRAT convergence is in the log** | the curve won't reach tol (B17). The Candela version already exists from the gate (B10, B12). Decide which video(s) first |
| **4 λ sensitivity** | E1, E3, E4, E5, E6 | yes | show the two component columns beside the ratio (E4); paired, not medians alone (E3); mark annihilated cells as undefined (E6); never "conserved" (A3); thr 0.05 stated (A8) |
| **5 Misfit sink, directly** | Candela `E` vs VIRAT `E` | **partly** | 🔴 **premise risk A24**: on Candela, `E` is 74.6% nonzero with only 13.4% of its nonzeros real noise (factor 1, §6.1). "Candela `E` = noise" is not clean in the record. A thresholded Candela `E`-precision is needed before the figure is designed. Spec wording (RESEARCH_PLAN:79 "lands on `S`'s background edges") is A2 |
| **6 Baseline comparison** | baseline `N` wins 180/180 at `lam_s=0.01, lam_n=0.001`; hybrid 0/180 | baseline side yes (`ARCHIVE_BASELINE.md`); **real-SS-RTD-vs-baseline comparison not run** | Phase 4 territory. No SS-RTD-vs-baseline number exists yet. Baseline `ssrtd_*` PSNR/SSIM columns are banned (~217 dB). `hybrid_compression_ratio` is unaudited |

**Tables**

| table | in the record? | note |
|---|---|---|
| real PSNR/SSIM vs proper reconstruction | noise condition only (F8). On clean VIRAT there is no ground truth | Phase 4 |
| λ behaviour | yes (§20.1) | E1–E8 |
| compression (hybrid negative result) | H.264 sizes are in the CSV for all 320 runs; **no analysis in the log** | Phase 4; baseline hybrid 0/180 from `ARCHIVE_BASELINE.md` |

---

## I. Gaps: numbers the manuscript will want that the record lacks

1. **A 180-video enrichment at threshold 0.01.** Only the subset's 4.7x exists (A9). The
   box analysis computed per-video 0.01 enrichment for 180 but recorded only correlations.
2. **A VIRAT convergence summary** (Figure 3).
3. **A thresholded Candela `E`-precision** (Figure 5's premise, A24).
4. **Real SS-RTD vs the naive baseline** on the same videos (Figure 6).
5. **Compression analysis** of the Phase 3 H.264 columns.
6. Whether the sink appears in the naive baseline, which would turn A20 from argument to
   measurement.
