# V2 STRUCTURE — what the revised paper needs, and where each part lives in the record

> A map, not a draft. Written 2026-11-24 for submission to **IEEE Access** (a journal, so
> v1's 4-page conference limit no longer applies). **The record wins.** Where this file
> disagrees with `RESEARCH_LOG.md` or `MANUSCRIPT_NUMBERS.md`, those are right.
> The companion audit is `paper/MANUSCRIPT_V1_AUDIT.md`. It gives the verdict on every v1
> claim. This file says where each v2 section's content comes from.

**Conventions.**
- § means a `RESEARCH_LOG.md` section.
- Codes like A1, B10, C2 and I.4 are rows of `MANUSCRIPT_NUMBERS.md`.
- PN n means `PAPER_NOTES.md` item n; AB §n means `ARCHIVE_BASELINE.md` section n.
- Every number quoted in v2 must come from a `MANUSCRIPT_NUMBERS.md` row, not from this
  file. The numbers below are signposts only.

**Provenance tags used in the section map:**

| tag | meaning |
|---|---|
| **FORWARD** | v1 content that carries into v2, possibly lightly edited (audit verdict SURVIVES) |
| **BASELINE** | v1 content that becomes the naive-baseline comparison, not the main result (audit verdict RELABEL) |
| **NEW** | not in v1; comes from Phase 3 onward |
| **GAP** | v2 needs it and the record does not have it yet |

---

## 0. The frame (settled; do not reopen)

**The contribution** (§23.1). The paper reports a property of a **model class**: in an
`L + S + E` decomposition (smooth foreground `S`, sparse noise `E`), when there is no noise
for `E` to represent, `E` claims `S`'s support far above chance. It acts as a **misfit
sink**. The supports coincide: median enrichment 47.4x, 180/180 videos (§19.1, C-rows).

**The transfer question is demoted** (§23.2). Running SS-RTD on surveillance video is how
the claim was obtained, not what the claim is about. Rule (§23.2): "the transfer test is
how the claim was obtained; the claim is about the model class." The introduction should
not be organised around "does an X-ray method transfer". See also audit §6 item 1: the
source paper already validated on surveillance-type clips (Candela, Caviar1, Caviar2) with
injected noise. The real difference from that validation is **no injected noise**, and that
is exactly what RQ1 is about.

**The research questions** (§23.1, as the brief states them):

| RQ | question | status | primary record |
|---|---|---|---|
| **RQ1** | Does `E` claim `S`'s support when there is no noise for `E` to represent? | answered: yes | §10, §19; C1–C10 |
| **RQ2** | Does λ remove the coincidence or relocate it? | answered: relocates; never removes | §20, §20.7; E1–E10 |
| **RQ3** | Does it depend on scene content? | answered: yes, a dose-response, but not localised to annotated objects | §19, §24, §25; D1–D10, G-rows |
| **RQ4** | Is it explained by `E` being idle? (pre-registered) | answered: no. Idleness refuted (§22); the sink is preserved under noise (§27, weak by design) | §21→§22, §26→§27; F3–F6, G6 |

**Compression is no longer a research question.** It survives as one secondary result
(the hybrid negative result, §VIII below). The title, abstract and introduction must not
lead with it.

**Enrichment is a threshold-0.05 statistic.** 47.4x is at threshold 0.05 (§9.4). Every
enrichment number must carry its threshold (A8). The threshold dependence is reported as a
robustness result (§20.7b, §25.5).

---

## 1. Section map at a glance

| v2 section | provenance | v1 source | record source |
|---|---|---|---|
| Title, abstract, index terms | NEW | — (v1 had no abstract) | §23.1 |
| I Introduction | NEW (v1 §I rewritten) | §I ¶1–2 background only | §23.1, §23.2 |
| II Related work | NEW (expanded) | §I ¶2–3, refs [3]–[7] | author's bibliography; reviewer (§2) |
| III Method | NEW | — (v1 §II.C RETRACTED in part) | `paper/SOURCE.md`; PN 1–3, 10–12, 14, 15, 17; §6, §7 |
| IV Experimental design | FORWARD + NEW | §III.A (dataset, preprocessing) | §8, §11, §21, §24 |
| V Results: RQ1 to RQ4 | NEW | — | §10–§27 |
| VI Robustness | NEW | — | §7.8, §14, §20.7, §25.5 |
| VII Comparison with the naive baseline | **BASELINE** | §II.E, §III.B, §III.D, Tables I–II, §IV.A–B, §V.A ¶1–2 | §3; AB §3–§4; PN 9, 13; §4 item 1 |
| VIII Compression (secondary) | **BASELINE** + FORWARD | Table III, §IV.C | AB §4; §4 item 8; audit §6 items 2–3 |
| IX Discussion | NEW | §V.C ¶2 (scoped) | §23, PN 18, A20 |
| X Limitations | FORWARD + NEW | §V.B | various (§X below) |
| XI Conclusion | NEW | — | §23.1 |
| Data and code availability | FORWARD (updated) | §III.E | §28, §30.3, manifest |
| AI-use disclosure | NEW | — | `AI_DISCLOSURE_FACTS.md` |
| Note on the earlier version | NEW | — | §1, §4 item 1, §4 item 5 |

---

## 2. Section by section

### Title, abstract, index terms — NEW

- **Title.** Name the finding: the misfit sink, or support coincidence of the noise
  component when there is no noise to model. It should not use "component collapse",
  which is the baseline's property (audit §4), and should not lead with compression.
- **Abstract.** RQ1–RQ4 with one headline number each, threshold-scoped:
  - RQ1: C-rows;
  - RQ2: E-rows;
  - RQ3: D-rows;
  - RQ4: F3–F6 and G6.

  The abstract also needs one sentence on verification (§6 gate) and one on the baseline
  contrast.
- **Index terms.** Required by IEEE Access. Absent in v1.

### I Introduction — NEW (rewritten)

| ¶ | content | source |
|---|---|---|
| 1 | Background/foreground decomposition: RPCA → tensor RPCA → three-component models with a dedicated noise term | v1 §I ¶2 (FORWARD, with "noise" in place of "residual"; audit §2.2 #1) |
| 2 | The design premise of `L + S + E`: `E` exists to absorb noise. What happens when the data carry none? | §23.1 |
| 3 | SS-RTD as the instance studied. Designed for noisy X-ray AM video; validated on surveillance and traffic clips (Candela, Caviar1/2, CDnet) with 10–30% impulse noise. VIRAT here has **no noise** | `paper/SOURCE.md`; §32.1 |
| 4 | RQ1–RQ4, verbatim from §0 above | §23.1 |
| 5 | Contributions. One bullet per RQ, plus verification of a faithful reimplementation, plus the baseline contrast. The bullets must not overlap (reviewer Major 4, §2) | §23.1 contribution table |

**Do not carry forward** from v1 §I:
- "validated on X-ray imaging data" (audit §5, §I ¶4);
- "whether the third component helps on compressing surveillance video" (audit: SUPERSEDED);
- "systematically collapses to two" (audit: RELABEL);
- contribution bullets C1–C3 as written.

### II Related work — NEW (expanded)

The reviewer flagged 7 references as sparse (§2, minor). Needed threads:
1. matrix RPCA and its variants;
2. tensor RPCA (Lu et al.);
3. three-component / noise-aware decompositions (Shen et al.; others the author selects);
4. TV-regularised foreground models;
5. RPCA-based surveillance compression;
6. **component identifiability / degeneracy** in multi-term sparse models. This is the
   literature the misfit-sink finding speaks to.

Source: the author's bibliography. `AI_DISCLOSURE_FACTS.md` records that no reference was
chosen by the agent, so this stays the author's choice. Every reference passes
`src/verify_refs.py`. Shen et al. is cited as **2023** (§29.1), with pages checked against
Crossref (`ISSUE_VERSION_CHECKLIST.md` row 0.2; audit §2.4).

### III Method — NEW

v1 has no usable counterpart. v1 §II.C's smoothness paragraph is RETRACTED (audit §2.1).

| subsection | content | source |
|---|---|---|
| III.A Model | `X = L + S + E`; Tucker/HOOI `L`; anisotropic spatio-temporal TV on `S`; L1 on `E`; one λ | `paper/SOURCE.md` eqs. (3)–(4); PN 3 |
| III.B Algorithm | ADMM updates: HOOI (eq. 8), FFT S-update (eqs. 9–11), soft-threshold `E`, adaptive conditional penalties (eq. 14: c1 1.15, c2 0.95, γ 1.1) | `paper/SOURCE.md`; `src/ssrtd_real.py` |
| III.C Implementation decisions and disclosures | Every place the paper is ambiguous or inconsistent, and the choice made: rank rule and the clamp to (144, 144, 1) (PN 1; §5); eq. 12 threshold, printed 2/β against Appendix A 1/β (PN 11); stopping rule and the 100-iteration cap governing (PN 14; B17); PSNR formula (PN 15); `factor = 1.0` (§6); the rest of PN 2, 10, 12, 17 | B1–B8; PN as listed |
| III.D Verification | The gate: reproduction of the source paper's Fig. 3 on SBI Candela (relErr_L 0.0628 vs 0.0626; PSNR 42.83 vs 43.27); 248 assertions; not bitwise across FFT backends (§6.6), robust in outcome (§7.8) | §6, §7.7, §7.8; B10–B13 |
| III.E The enrichment statistic | `P(E\|S)/P(E)`, with its definition, threshold (0.05 primary, 0.01 secondary), and what it does and does not measure | §9.4; §20.7b; §25.5; A8, A9 |
| III.F Caveat on the source version | Verification used the early-access PDF; the provisional rigor findings (PN 1, 11, 14, 15) | §29.2, §30.1; `ISSUE_VERSION_CHECKLIST.md` |

**Must be resolved before submission:** `ISSUE_VERSION_CHECKLIST.md`, which checks the
issue version against the early-access PDF. Until then III.C and III.F carry the
"provisional" wording.

### IV Experimental design — FORWARD + NEW

| subsection | content | provenance | source |
|---|---|---|---|
| IV.A Dataset | VIRAT Ground 2.0 videos-01, 180 videos, 1280×720, 23.97 fps, ≥300 frames; first 300 | **FORWARD** (v1 §III.A, audit: SURVIVES) | §24.1 |
| IV.B Preprocessing | grayscale; INTER_AREA to 320×180; /255 | **FORWARD** (v1 §II.B, minus "color adds no benefit", which is ORPHANED) | `preprocessing.py:21-22`; §24.2 |
| IV.C Conditions and arms | clean (180) and noise (20); λ grid; factor 2.0; the six arms and 320 runs in total, with which video subset each uses | NEW | §8, §11, §21.6, §22.5 |
| IV.D The 20-video subset | how it was chosen (16 by rank of the temporal-change statistic plus the 4 busiest); no selection effect on the headline (§19) | **FORWARD** as design (v1 §III.D), with the statistic renamed "temporal change", not "foreground density" (A1; §25.1) | §8; §19 |
| IV.E Noise model | 10% random-valued impulse noise, the lowest of the source paper's validation ratios (10–30%, §32.1) | NEW | §12, §21 |
| IV.F Annotations | VIRAT object annotations; `box_occupancy` | NEW | §24; G1–G7 |
| IV.G Pre-registrations | §21 (commit `63913fb`) and §26 (commit `3b59daf`), committed before their results | NEW | §21, §26 |

### V Results — NEW. The main result

One subsection per RQ, in order.

**V.A RQ1: does `E` claim `S`'s support with no noise to represent?**
- 180/180 above 1; median 47.4x (range 2.4–453.3) at threshold 0.05 (§19.1; C-rows).
- First seen on the 20-video subset: 40.4x, 20/20, odds ratio 94x (§10). Superseded in
  scale by §19, not in substance.
- Rest-of-set figure, 49.0x: no selection effect (§19).
- The noise-condition corroboration belongs under RQ4 (F2).
- Figures: decomposition panels (Fig. 2) and the enrichment distribution (H rows).

**V.B RQ2: does λ remove or relocate it?**
- Sweep from 29.4x to 55.0x; 96/96 runs above 1 (§20.1).
- `S` holds 6.1x fewer voxels and `E` 2.8x more across the grid (§20.2).
- `S` annihilation at high λ (§20.3).
- Ordering preserved, ρ +0.93 to +0.99 (§20.4).
- Paired ratios 1.14, 1.22, 1.29 (E-rows).
- Not conserved: `E` gains about twice what `S` loses (§20.7).
- λ 0.4 sits near the conservative end of the recommended range.
- **Answer: relocated, never removed.**
- Figure 4 (λ sensitivity).
- Caution: the §20.7 n-mismatch (n = 20 vs n = 17) must be stated with the slope (§31).

**V.C RQ3: does it depend on scene content?**
- Dose-response: ρ −0.508 against the temporal-change statistic; slopes −0.517 and −0.537
  (§19; D-rows).
- The statistic is **not** foreground amount: against annotated occupancy, ρ +0.382 and
  Pearson −0.057 (§25.1).
- Against occupancy directly: ρ −0.329 / −0.234 (§25).
- **Report the negative:** localisation onto annotated objects is NOT SUPPORTED (31.5% vs
  29.8%, §25.4).
- The 19x asymmetry is **exploratory** and must be labelled so (§25.6).
- The `video_101` case (§25).
- `video_01` is the weakest (2.4x; §10).

**V.D RQ4: is it explained by `E` being idle? (pre-registered)**
- Pre-registration §21; result §22. Under noise the sink is not dissolved: 1.263x noise vs
  1.267x clean; CI 1.151–1.387; 17/20; p 2.58e-03. The corrupted-voxel ratios are
  0.987 and 0.994. **Idleness refuted** (F3–F6).
- Pre-registration §26; result §27: PRESERVED, r* 1.061 (0.988–1.138). The test was weak
  by design; say so (G6).
- Supporting: the noise condition at 41.9x; ρ +0.994; +20.35 dB PSNR gain from `E`
  absorbing real noise (§12; F2, F8). This shows `E` does its intended job when noise is
  present.
- §12.2 lists retractions inside that work. Do not quote retracted §12 figures.

### VI Robustness — NEW

| check | result | source |
|---|---|---|
| ADMM factor 2.0 instead of 1.0 | 21.9x, ρ +0.847: weaker, same sign | §14 |
| FFT backend | not bitwise identical; outcome robust | §6.6, §7.8 |
| threshold 0.05 vs 0.01 | level changes (4.7x vs 40.4x on the subset); slope robust (1.240 vs 1.290) | §20.7b; §25.5; A9 |
| convergence | `relChg_L` plateau; the 100-iteration cap governs on VIRAT | §6.3; B17; PN 4 |

**GAPS:**
- I.1: no 180-video enrichment at threshold 0.01;
- I.2: no VIRAT convergence summary (Fig. 3 needs it).

### VII Comparison with the naive three-component baseline — **BASELINE** (v1's main result, demoted)

This is where v1's main content goes. It answers "is the misfit sink specific to faithful
SS-RTD, or a generic artefact of three-component formulations?" and it shows why the
earlier result was not about SS-RTD.

| part | content | v1 source | record source |
|---|---|---|---|
| VII.A What the baseline is | `src/ssrtd.py`: SVT-averaged `L`, two L1 terms `S`, `N` at `lam_s`/`lam_n`, open-loop `mu ×1.5` capped at 1e6. **All four divergences** from SS-RTD, plus the stopping rule. State plainly that it is a different algorithm, not an ablation | replaces v1 §II.C, §II.E, §III.B | §4 item 1; audit §2.3; AB §1–§2 |
| VII.B Winner-takes-all on 180 videos | `N` 180/180; `S` median 0.10% non-zero; `N` 99.95%. Must say the setting used was the most collapse-forcing one (§4 item 3) | **BASELINE**: v1 Table I, §IV.A, contribution 1 | §3.1; AB §3 |
| VII.C The ratio mechanism | 20 videos × 5 configurations, unanimous winners; the equality case is update order (`S` before `N`); deterministic. Merged with VII.B as one mechanism (reviewer Major 4). Rows in numeric order (reviewer minor) | **BASELINE**: v1 Table II, §IV.B, contribution 2, §V.A ¶2 | §3.2, §3.3 |
| VII.D Why: an expected outcome | Two interchangeable L1 penalties competing for one residual select one winner by the ratio. Predictable from soft-thresholding (reviewer, Novelty). Candidate second mechanism: the penalty ramp (PN 13, unmeasured; see audit §6 item 4 on the sweep's 32 iterations) | v1 §V.A ¶2, §V.C ¶2 (scoped) | §4 item 1; PN 13 |
| VII.E The contrast with SS-RTD | baseline: one of `S`, `N` is empty and the parameter ratio decides. SS-RTD: both non-empty, supports coincide far above chance, the scene sets the ordering | — | audit §3; §19, §20 |

**GAPS (blocking for VII.E as a measured comparison):**
- **I.4**: no real-SS-RTD vs baseline run on a common metric.
- **I.6**: enrichment of the baseline's `S`/`N` not computed. It is untested whether the
  sink appears in the naive baseline.
- The 180-video baseline batch's iteration counts were never recorded (§4 item 1,
  "Blocker"). They are needed for any claim that PN 13's saturation affected the batch.

Without I.4 and I.6, VII.E can only juxtapose two separately measured statements. It must
say so.

### VIII Compression — secondary result — **BASELINE** + FORWARD

**Author's decision (open):** a short results section or an appendix. Either way it is
not an RQ.

| part | content | source |
|---|---|---|
| hybrid negative result | Tensor-RPCA `L` plus the baseline's `N`, H.264: 0/180 smaller; 1.35x–1.87x, mean 1.55x. **CRF 28 on both sides** | AB §4; §4 item 8; v1 Table III, §IV.C; audit §6 item 2 |
| `L` alone | 176/180 smaller, mean 6.8% (CRF 28 both sides). Must address reviewer Major 3: static background against full video | v1 Table III; §2 |
| CRF statement | Against the CRF-23 reference both `L` and the hybrid are smaller on 180/180; the result depends on the matched-CRF comparison | audit §6 item 2 (**not yet in the record**) |
| hybrid PSNR | median 30.70 dB is the only valid baseline PSNR | AB §3 |

**Must not appear:**
- `ssrtd_psnr`, `ssrtd_ssim`, `tensor_psnr`, `tensor_ssim` (~217 dB; tautological; §1,
  AB §3);
- `hybrid_compression_ratio` as a result (audit §6 item 3);
- "foreground is dense" as the explanation (audit: ORPHANED†).

**GAP I.5:** no compression analysis of the Phase 3 H.264 columns for real SS-RTD. Either
run it or state that compression was measured for the baseline only.

### IX Discussion — NEW

| ¶ | content | source |
|---|---|---|
| 1 | What the misfit sink means for the model class: a dedicated noise term without noise to absorb becomes a second foreground term | §23.1; PN 18 |
| 2 | Why the TV/L1 split invites it (a DC-bin and spectral account, if kept) | PN 8 |
| 3 | Scope. Measured on one model, one dataset, one instrument; the generalisation is a hypothesis | **A20**; reviewer Major 5 |
| 4 | Practical consequence: diagnose `E` before trusting `S` as foreground; a check practitioners can run | v1 §V.C ¶2 (the "check for collapse" advice, re-scoped) |
| 5 | The baseline lesson, scoped to two interchangeable L1 terms | §4 item 1; PN 9 |

**Do not carry forward:**
- "practitioners should focus on the background";
- "Tensor RPCA may give the same effective result";
- "temporally stable" as the reason `L` compresses.

All three are ORPHANED (audit §5).

### X Limitations — FORWARD + NEW

| limitation | provenance | source |
|---|---|---|
| VIRAT only, outdoor | FORWARD (v1 §V.B) | — |
| grayscale, 320×180, 300 frames; no sensitivity analysis on resolution or length | FORWARD (v1 §V.B; reviewer minor) | §5 (rank, frames) |
| H.264 only (for §VIII) | FORWARD | — |
| λ sweep and noise condition on a 20-video subset | NEW | §8, §20, §22 |
| one noise type (impulse), one rate | NEW | §12, §21 |
| one instrument for enrichment; any `L+S+E` claim is measured on it alone | NEW | **A20** |
| voxels are spatially and temporally autocorrelated, so voxel-level p-values overstate independence | NEW | the relevant §20/§22 inference notes |
| verification against the early-access source version | NEW | §29.2, §30.1 |
| the 100-iteration cap governs on VIRAT | NEW | B17; PN 4, PN 14 |
| the premise that Candela's `E` is real noise | NEW | **A24**; §6 (74.6% non-zero, 13.4% real noise) |
| **delete:** "results for SS-RTD are without the smoothness term" | RETRACTED | audit §2.1 |

**GAP I.3:** thresholded Candela E-precision is not computed. It is needed to state the
A24 premise quantitatively.

### XI Conclusion — NEW

Restate RQ1–RQ4 answers in one line each, give the baseline contrast in one line, then
future work:
1. other three-component models;
2. other datasets;
3. graded noise levels;
4. other codecs.

v1's "other three-component methods" question is SUPERSEDED in its v1 form (audit §5, §VI).

### Data and code availability — FORWARD (updated)

- Repository URL: FORWARD from v1 §III.E.
- Environment: Python 3.12.3, NumPy 2.4.6, SciPy 1.17.1 for Phase 3, from the manifest
  (`results/metrics/ssrtd_real_manifest.json`). v1's "Python 3.12" is unrecorded for the
  2026-06 baseline runs (audit §5, §III.E).
- Analysis scripts are in `src/analysis/` (§28, §30.3).
- Frozen baseline CSVs with SHA256 (AB §5).
- **Blocker before citing the repository:** `src/ssrtd.py:48,55` and `README.md:12,35`
  still carry the retracted overflow claim and the "SS-RTD" label (§4 item 9; audit §2.1).

### AI-use disclosure — NEW

IEEE requires it, and v1 had none. Content comes from `AI_DISCLOSURE_FACTS.md`:
- what the agent did;
- that the bibliography is the author's;
- that pre-pivot code authorship cannot be determined.

### Note on the earlier version — NEW

The record (§1, §4 item 5) requires the correction to be explicit:
- the v1 method was a different algorithm, not SS-RTD;
- the smoothness penalty was never implemented;
- the overflow rationale has no artifact.

Where it goes (a footnote, a short paragraph in §III or §VII, or the response letter only)
is the author's and editor's call. Policy differs between a fresh submission and a
resubmission. The response letter must address reviewer Major 1 directly. The suggested
remedies (gradient clipping, rescaling) presume an overflow that never happened (audit
§2.1).

---

## 3. Figures and tables

Planned set: `MANUSCRIPT_NUMBERS.md` H rows; `RESEARCH_PLAN.md` Phase 5.

| # | content | section | status |
|---|---|---|---|
| Fig. 1 | Pipeline with three branches (SS-RTD → `L, S, E`; baseline → `L, S, N`; Tensor RPCA → `L, S`) | III / IV | redraw; v1 Fig. 1 is RELABEL (audit §5) |
| Fig. 2 | Decomposition panels with `S`/`E` support overlap | V.A | from Phase 3 outputs |
| Fig. 3 | Convergence on VIRAT | VI | **GAP I.2** |
| Fig. 4 | λ sensitivity: enrichment and support sizes against λ | V.B | §20 |
| Fig. 5 | Misfit sink: Candela vs VIRAT `E` | V.A / X | premise unestablished (**A24**, **I.3**) |
| Fig. 6 | Baseline comparison | VII | **GAPS I.4, I.6** |
| Table | Implementation disclosures (paper vs implementation) | III.C | PN items; B-rows |
| Table | Verification gate | III.D | §6 |
| Table | RQ1 headline, 180 videos | V.A | C-rows |
| Table | λ behaviour | V.B | E-rows |
| Table | Noise / idleness pre-registered result | V.D | F-rows, G6 |
| Table | Four divergences, SS-RTD vs baseline | VII.A | §4 item 1; audit §2.3 |
| Table | Baseline winners: v1 Tables I+II merged, rows in numeric order | VII.B–C | §3.1–§3.2 |
| Table | Compression, CRF stated | VIII | v1 Table III; AB §4 |

---

## 4. v1 → v2 in one view

| v1 section | fate | v2 location |
|---|---|---|
| Title | SUPERSEDED | new title |
| §I Introduction | background FORWARD; framing and contributions replaced | §I |
| §II.A Overview | RELABEL | §III / §IV |
| §II.B Preprocessing | FORWARD | §IV.B |
| §II.C Decomposition: RPCA/Tensor RPCA | FORWARD | §II / §VII |
| §II.C smoothness paragraph | **RETRACTED** | deleted; the correction note |
| §II.D Compression measurement | FORWARD (description only) | §VIII |
| §II.E Parameter analysis | **BASELINE** | §VII.C |
| Fig. 1 | RELABEL | Fig. 1 redrawn |
| §III.A Dataset | FORWARD | §IV.A |
| §III.B Implementation | Tensor RPCA FORWARD; "SS-RTD" settings **BASELINE**; overflow sentence RETRACTED | §VII.A |
| §III.C Compression setup | FORWARD, with the CRF stated | §VIII |
| §III.D Sweep setup | **BASELINE**; subset design FORWARD | §VII.C, §IV.D |
| §III.E Reproducibility | FORWARD, updated | Data and code availability |
| Table I, §IV.A | **BASELINE** | §VII.B |
| Table II, §IV.B | **BASELINE** | §VII.C |
| Table III, §IV.C | **BASELINE** + FORWARD | §VIII |
| §V.A Interpretation | ¶2 **BASELINE** (scoped); ¶1 and ¶3 replaced | §VII.D; §IX |
| §V.B Limitations | FORWARD, minus the retracted sentence | §X |
| §V.C Implications | ¶2 FORWARD (scoped); ¶1 and ¶3 ORPHANED | §IX ¶4–5 |
| §VI Conclusion | replaced | §XI |
| References [1]–[7] | all re-verified; [5] → 2023 | §II and throughout |

---

## 5. Before the draft can be finished

Ordered by what blocks most.

1. **`ISSUE_VERSION_CHECKLIST.md`**: blocks III.C, III.F and the pages of ref. [5].
2. **Gaps I.4 and I.6** (baseline on the enrichment metric; head-to-head): block VII.E and
   Fig. 6. Without them VII is two separate descriptions, not a comparison.
3. **Gap I.2** (VIRAT convergence summary): blocks Fig. 3 and part of VI.
4. **Gaps I.1, I.3, I.5**: robustness at 0.01 on 180 videos; the A24 premise; compression
   for real SS-RTD. Each can instead be stated as a limitation, but rigor favours running
   them.
5. **Repository clean-up** (§4 item 9): `src/ssrtd.py` docstring and `README.md` labels,
   before v2 cites the repository.
6. ~~**Record updates proposed by the audit**~~ **Done 2026-11-24** (`RESEARCH_LOG.md`
   §32):
   - the validation-domain fact (§32.1);
   - the CRF-28 matching and the `hybrid_compression_ratio` semantics (§32.2);
   - the sweep's `n_iter = 32` and its effect on PN 13 (§32.3).
7. **Reference verification**: run `src/verify_refs.py` over the full bibliography;
   choosing references is the author's job.
8. **Author decisions:** where compression goes (§VIII vs appendix); where the
   correction note goes; the title.
