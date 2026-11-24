# MANUSCRIPT V1 AUDIT — the submitted manuscript against the record

> This is an audit, not a rewrite. It classifies every section, table, figure and claim of
> the previously submitted manuscript. Written 2026-11-24 against the record as of
> commit `7cc9b06`. **The record wins.** Where this file and `RESEARCH_LOG.md`
> disagree, the log is right and this file is wrong.

## 0. What was audited, and how

**The file.** `paper/Manuscript_V1.pdf`: 4 pages, sections I–VI, Figure 1, Tables I–III,
and references [1]–[7]. It has no abstract and no index terms.
- Its extracted text is identical to `An_empirical_Study_on_VIRAT.pdf`, committed in
  `d1b591b` (2026-09-08, "Add the current manuscript PDF (pre-pivot, built on the
  mislabeled method)").
- The binary differs. `paper/Manuscript_V1.pdf` carries a PDF creation date of
  2026-11-24, so it is a recompile of the same text.
- Text was extracted with PyMuPDF. Pages 2 and 3 were also rendered and read, because
  extraction garbles the equations and table rows.

**Every number was re-derived.** Each number in Tables I–III and §IV was recomputed from
`results/baseline_naive/all_results.csv` and `param_sweep.csv`. These files are read-only
and the SHA256-verified frozen copies (`ARCHIVE_BASELINE.md` §5). **All of them reproduce
exactly.** Nothing in v1 is a wrong number. What is wrong is what the numbers are
attributed to and what they are said to mean.

**Verdict codes** (from the brief):

| code | meaning |
|---|---|
| **SURVIVES** | true and still relevant, usable as-is |
| **RELABEL** | the finding holds, but it is attributed to SS-RTD when it belongs to the naive three-component baseline (`src/ssrtd.py`) |
| **RETRACTED** | contradicted by the record. The section that retracts it is cited |
| **SUPERSEDED** | a newer, larger-n or de-confounded result replaces it |
| **ORPHANED** | nothing in the current record supports it either way |

Two marks refine these:
- **ORPHANED†**: no record section addresses the claim, but data already in the record
  contradict it. It is not formally retracted, because nothing retracts it, yet it cannot
  be used.
- **[audit]**: something found during this audit that the record does not yet contain.
  These are collected in §6. None was written into the record, per the brief.

**Citations.** § means a `RESEARCH_LOG.md` section. Codes like A1 or C2 are rows of
`MANUSCRIPT_NUMBERS.md`. `PN n` means `PAPER_NOTES.md` item n. `AB §n` means
`ARCHIVE_BASELINE.md` section n. Locations in v1 are given as page, section and paragraph
(¶).

---

## 1. Summary

| verdict | count | where the weight is |
|---|---|---|
| SURVIVES | 25 | dataset and preprocessing, every number in Tables I–III, the baseline's parameter-ratio mechanism, the hybrid negative result, most limitations |
| RELABEL | 24 | the main result: the 180-video "collapse", the 20×5 sweep, contributions 1–3, the Discussion and the Conclusion. All of it is the baseline's |
| RETRACTED | 4 | the smoothness-penalty paragraph in II.C, its echo in III.B, its echo in V.B, and the overflow mechanism |
| SUPERSEDED | 7 | the title's framing, the "foreground-density" naming, "the original method might behave differently", the future-work question, the parameter-sensitivity claim about SS-RTD |
| ORPHANED / ORPHANED† | 22 | motivation and literature claims, references [1]–[4], [6] and [7], promised PSNR/SSIM, the compression explanations, "validated on X-ray" |

Counts are of rows in §§2–5. Some rows carry two verdicts, one for the baseline reading
and one for the SS-RTD reading, so the counts are approximate.

**Three findings the revision must confront, in order of severity:**

1. **v1 describes a removal that never happened** and gives it a mechanism (§2.1). This is
   the issue the reviewer's Major Problem 1 rests on. The reviewer accepted the removal as
   fact and asked for an alternative fix. The truthful answer is that no penalty ever
   existed in the code, so there was nothing to fix.
2. **Every result is the naive baseline's**, and v1 names it "SS-RTD" 21 times (§2.2).
3. **v1 says SS-RTD was "designed and validated on X-ray imaging data"** [audit]. The
   source paper motivates the method with X-ray additive-manufacturing (AM) video, but its
   §IV validates it on SBI Candela, Caviar1 and Caviar2 and on CDnet Highway, Office and
   Pedestrians. These are surveillance and traffic clips with 10–30% synthetic impulse
   noise, and the gate (§6) uses the first of them (`RESEARCH_LOG.md` §32.1). The record repeats the same simplification (`CLAUDE.md`, `START_HERE.md`, §23.2),
   so the issue reaches beyond v1 (§6 item 1).

---

## 2. The four items requested explicitly

### 2.1 Section II.C's smoothness-penalty paragraph: what the paper claims vs what git shows

**What v1 says.** It says it in three places.

| where | exact text |
|---|---|
| p.2, §II.C, ¶1 (second half) | "SS-RTD includes a penalty encouraging the foreground component to be spatially smooth, which is appropriate for its original domain (X-ray imaging) but not for surveillance video. We therefore disable this penalty, because foreground objects in surveillance video have sharp edges. The penalty tries to force smoothness onto a signal that is inherently sharp; the optimizer pushes values to extremes to satisfy an impossible constraint, and these values grow until they exceed the range representable in floating-point arithmetic, causing numerical overflow." |
| p.2, §III.B, last sentence | "We remove the smoothness penalty from SS-RTD because it causes float64 overflow on the sharp-edged foreground typical of surveillance video." |
| p.3, §V.B, ¶1 | "Our results for SS-RTD are without the smoothness term, we disabled it. The original method might behave differently." |

**The paragraph makes six separable claims.** They are scored one by one, because they do
not share a verdict.

| # | claim | verdict | basis |
|---|---|---|---|
| 1 | SS-RTD has a penalty that encourages a smooth foreground | **SURVIVES, with a correction** | True of the *published* method. It is anisotropic total variation on `S`, eq. (4) (`paper/SOURCE.md`), and it is **spatio-temporal** (horizontal, vertical **and temporal** differences), not "spatial" only. §4 item 1 |
| 2 | that penalty is appropriate for X-ray but not for surveillance video | **ORPHANED**, and contradicted by the source paper [audit] | No evidence in the record either way, as an a-priori claim. The source paper validates SS-RTD on SBI Candela/Caviar clips with walking people treated as smooth foreground (§IV-B). The real TV term then ran on all 180 VIRAT videos without numerical failure (below) |
| 3 | **"We therefore disable this penalty"** / "We remove" / "we disabled it" | **RETRACTED** (§1; §4 item 5) | Nothing was disabled. The code never contained it (below) |
| 4 | the reason: surveillance foreground has sharp edges | **RETRACTED** as a reason | It is the rationale for an action that did not occur (§4 item 5). As a description of VIRAT it is not established either: "edges" is a visual reading of one frame (§7.4; A19) |
| 5 | **the mechanism**: the optimizer pushes values to extremes to satisfy "an impossible constraint", the values grow, float64 overflows | **RETRACTED** (§1: "an undocumented claim with no artifact in this repo — no code, no log, no failing run"; §4 item 5: "Delete it rather than trying to substantiate it") | Three further problems. (i) TV here is a **penalty**, not a constraint, so there is no constraint to be "impossible". (ii) In the real algorithm the TV proximal step is a soft-threshold (eq. 11), which cannot grow values. The S-update is a linear FFT solve whose denominator is bounded below by β_X at every frequency (PN 8: `denom.min() == beta_X`). (iii) Real SS-RTD with the TV term ran **320 times on VIRAT in float64 with zero numerical failures** (§10, §12, §14, §19, §20, §22.5), and `err_X` converged from 177 to 0.58 on `video_01` (§7.3) |
| 6 | the results are "without the smoothness term" and "the original method might behave differently" | first half **RETRACTED**; second half **SUPERSEDED** (§6, §10–§22) | Without the smoothness term: yes, but not because the term was removed. The method run had no such term because it was never SS-RTD (§4 item 1). Whether the original behaves differently was tested: it does (see §3 of this file) |

**What git shows.** Each item below was re-verified on 2026-11-24 with the commands in the
log's "Verification provenance" section.

1. **The claim is older than the code.** The initial commit `6a7878e` (2026-06-07) adds
   `CLAUDE.md`. Its line 30 already reads: `SS-RTD: lam_s=0.001, lam_n=0.002, smoothness
   penalty REMOVED (caused overflow)`. At that moment `src/ssrtd.py` did not exist.
2. **The code was born without the penalty.** `d7a786e` (2026-06-07, "Add SS-RTD module —
   smoothness penalty removed, three-component decomposition verified") **creates**
   `src/ssrtd.py`. Its first version already contains:
   - the docstring "Smoothness penalty from original paper removed: causes float64 overflow
     on sharp-edged human foreground in surveillance domain. Documented as a
     domain-transfer finding of this research";
   - the three-update loop still in use today: `L = tensor_svt(...)`,
     `S = soft_threshold(..., lam_s/mu)`, `N = soft_threshold(..., lam_n/mu)`,
     `mu = min(mu*1.5, 1e6)`.

   There is no earlier version to have removed anything from.
3. **Only two blobs of `src/ssrtd.py` have ever existed**: `ffdce15` and `cfbd7ea`. The
   only change between them, `75fa46f` (2026-06-08), is the default `lam_s`/`lam_n` in one
   signature line.
4. **Pickaxe over all history, restricted to code** (`git log -S smooth --all -- '*.py'`):
   - The only pre-pivot hit is `d7a786e`, the commit that wrote the "removed" docstring.
   - Every later hit is the post-pivot `src/ssrtd_real.py`, its tests and the runner.
   - `lam_t` and `total_variation` occur only in `6ed9350`, the pivot's documentation
     commit.
   - §1 records no stash, no other branch and a clean `git fsck`.
5. **No artifact anywhere** records an overflow: no log, no traceback and no failing run
   (§1).

**What the revision has to say, and what it must avoid:**
- It must not say "we restored the penalty" or "we fixed the overflow". Both imply the
  penalty once existed and the overflow once happened. Git shows neither.
- It must not keep "SS-RTD without its smoothness term" as a description of the old
  method. That still implies an ablation of SS-RTD. The old method differs in four
  structural ways, and the smoothness term is only one of them (§2.3).
- It must state that the v1 statement was **wrong**, not "inaccurate":
  - no smoothness penalty was ever implemented;
  - the overflow rationale has no supporting artifact;
  - the method v1 reported was a different algorithm.
- It must report what replaced it:
  - a faithful reimplementation, verified component by component (248 assertions, §7.7);
  - reproduction of the source paper's Fig. 3 on its own data (§6);
  - 320 VIRAT runs with the TV term and no numerical failure.
- **The reviewer's suggested remedy no longer applies.** The reviewer proposed gradient
  clipping, rescaling or a bounded smoothness penalty, with a comparison (§2, "Consistency
  of Methodology"). That presumes an overflow that never occurred. The response letter
  should say so directly, not implement the remedy.
- **The public repository still carries the claim.** v1's §III.E links to the GitHub
  repository, and `src/ssrtd.py:48,55` still says "smoothness penalty removed … causes
  float64 overflow". `README.md:12,35` still labels the baseline "SS-RTD". §4 item 9 lists
  both as ⏳ pending. A v2 that cites the repository while this text stands would repeat the
  retracted claim in its own artifact.

### 2.2 Every "SS-RTD" in v1

There are 21 occurrences: 20 in the extracted text, plus one split by hyphenation
("SS-/RTD", p.1). The title, table captions and references contain none.

Key:
- **→ baseline**: replace with "the naive three-component baseline", or the name it gets in
  Phase 2 (§4 item 9, "A real name for the baseline").
- **STAY**: the sentence refers to the published method, so the name stays.
- **STAY, correct**: the name is right but the content is not.

| # | location | text (abridged) | decision |
|---|---|---|---|
| 1 | p.1, §I ¶2 | "three-component forms such as SS-RTD add a third term to capture noise or residual [5]" | **STAY, correct**: the published third term `E` models **noise** (sparse, L1), not "residual". Shen et al. call it "noise" throughout |
| 2 | p.1, §I ¶4 | "SS-RTD was designed and validated on X-ray imaging data, where foreground is smooth" | **STAY, correct**: designed for noisy X-ray AM video, but validated on SBI Candela, Caviar1, Caviar2 and CDnet clips with injected noise (§IV); X-ray is the §V application [§6 item 1; `RESEARCH_LOG.md` §32.1] |
| 3 | p.1, §I ¶5 | "running Tensor RPCA and SS-RTD" | **→ baseline** |
| 4 | p.1, contribution 3 | "the hybrid combination of L and SS-RTD's foreground-carrying component N" | **→ baseline** (`N` is the baseline's second L1 term; AB §6) |
| 5 | p.2, §II.C ¶1 | "SS-RTD adds a third component N to capture noise or residual" | **→ baseline**. Published SS-RTD has no `N`. Its components are `L` (Tucker), `S` (TV-smooth foreground) and `E` (L1 noise) |
| 6 | p.2, §II.C ¶1 | "SS-RTD includes a penalty encouraging the foreground component to be spatially smooth…" | **STAY, correct** ("spatio-temporal", not "spatial"). The rest of that paragraph is RETRACTED (§2.1) |
| 7 | p.2, §II.E | "SS-RTD has trade-off parameters that control how strongly each component is penalized" | **→ baseline**. Published SS-RTD has exactly one parameter, λ ∈ [0.2, 1] (`paper/SOURCE.md`) |
| 8 | p.2, §II.E | "whether SS-RTD's behavior is controlled by the parameters or by the content" | **→ baseline** |
| 9 | p.2, Fig. 1 | box labelled "SS-RTD" producing "L, S, N" | **→ baseline** (§5, Fig. 1) |
| 10 | p.2, §III.B | "We run Tensor RPCA and SS-RTD (Smooth Sparse Robust Tensor Decomposition)" | **→ baseline**. The expansion is the published method's own name (Shen et al., abstract), so it can never be attached to the baseline |
| 11 | p.2, §III.B | "SS-RTD computes L + S + N" | **→ baseline** |
| 12 | p.2, §III.B | "For SS-RTD, we use λs = 0.01 and λn = 0.001" | **→ baseline** (§1, "Parameters used in the main 180-video batch"; `CLAUDE.md`: "the baseline's setting, not 'the method's'") |
| 13 | p.2, §III.B | "We remove the smoothness penalty from SS-RTD because it causes float64 overflow" | **delete**: RETRACTED (§2.1). Relabelling does not rescue it |
| 14 | p.3, §V ¶1 | "The SS-RTD's three component decomposition collapses to two" | **→ baseline** |
| 15 | p.3, §V.A ¶1 | "SS-RTD is designed to capture smooth foreground in S and noise in N" | **STAY, correct**: "…smooth foreground in `S` and noise in `E`". The sentences after it describe the baseline and must say so |
| 16 | p.3, §V.A ¶1 | "SS-RTD's third component was meant to separate noise from foreground" | **STAY** as the published design intent. The evidence that follows ("they don't separate at all") is the baseline's → baseline |
| 17 | p.3, §V.B | "Our results for SS-RTD are without the smoothness term, we disabled it" | **delete**: RETRACTED (§2.1) |
| 18 | p.4, §V.C ¶1 | "The third component of SS-RTD does not give any meaningful separation" | **→ baseline**. As a claim about SS-RTD it is not supported (§3) |
| 19 | p.4, §VI | "We've studied Tensor RPCA and SS-RTD on 180 surveillance videos" | **→ baseline** in a sentence about v1's work. In v2, real SS-RTD **was** run on 180 videos (§19), so the sentence becomes true again only about the new runs |
| 20 | p.4, §VI | "We found SS-RTD's three component decomposition collapses to two" | **→ baseline** |
| 21 | p.4, §VI | "examine whether other three component methods show the same behavior as SS-RTD" | **→ baseline** (the behaviour meant is the baseline's collapse). The question is also SUPERSEDED: Phase 3 ran the published method |

Tally: 13 → baseline, 6 STAY (5 of which need a content correction), 2 delete.

Not "SS-RTD", but carrying the same misattribution:
- the title ("Component collapse in Three-Component Tensor Decomposition…");
- Table I's caption ("the residual component N");
- Table III's "Hybrid (L+N)".

Each is covered in §5.

### 2.3 Divergences from Shen et al.: v1 states one, the record documents four

**What v1 states.** One divergence: the smoothness term is absent. v1 presents it as a
deliberate removal, which is false (§2.1).

**What §4 item 1 documents.** Its conclusion: "Not one of the four defining elements —
Tucker/HOOI low-rank, anisotropic-TV smoothness, single λ, adaptive conditional penalty —
is present." Its comparison table also marks two more rows as only partial matches (~).

For v1 to have been accurate, it would have had to say all of the following.

| # | published SS-RTD (`paper/SOURCE.md`) | what v1's method actually did (`src/ssrtd.py`) | kind |
|---|---|---|---|
| 1 | `L` = **Tucker decomposition via HOOI**, ranks (⌈0.8H⌉, ⌈0.8W⌉, 1), eqs. (3), (8) | `L` = singular-value thresholding on each of the three mode unfoldings, **refolded and averaged** (`ssrtd.py:29-39`) | objective (low-rank model) |
| 2 | `S` = smooth foreground, penalised by **anisotropic total variation** `λ‖S‖_TV1`, eq. (4), solved through the auxiliary `f` and an FFT S-update, eqs. (9)–(11) | `S` = **plain elementwise soft-threshold** at `lam_s/mu` (`ssrtd.py:87`). No TV, no smoothness of any kind | objective (smooth term absent) |
| 3 | **one** sparse term, `‖E‖_1` (noise); **one** tuning parameter λ ∈ [0.2, 1] | **two** independent L1 terms, `S` and `N`, with **two** parameters `lam_s`, `lam_n` (0.01 / 0.001) | objective (an extra, duplicated sparse term; two parameters in place of one) |
| 4 | **adaptive, conditional** penalty update, eq. (14): β grows by c1 = 1.15 **only if** the residual fails to shrink by c2 = 0.95; γ = 1.1; no cap | **open-loop geometric ramp**: `mu = min(mu*1.5, 1e6)` every iteration, whatever the progress (`ssrtd.py:75,90`) | solver |

Partial matches in the same table (~), which an accurate methods section would also
state:

| | published | `src/ssrtd.py` |
|---|---|---|
| stopping rule | relative change in `E` < 1e-6, at most 100 iterations (Algorithm 1) | relative change in `L` < 1e-7, at most 500 iterations (`ssrtd.py:69`) |
| sparse term | `‖E‖_1`, threshold `2/β_X` as printed (`1/β_X` per Appendix A; PN 11) | `soft_threshold(·, lam_s/mu)`, the same operator family with a different threshold rule |
| initialisation | Algorithm 1: `L` from the Tucker approximation of `X`, `S = X − L`, `β_f = 10/mean(X)`, `β_X = 0.4/mean(X)`, everything else 0 | all components zero, `mu_0 = 1/(√max(dim)·mean|X|)` (`ssrtd.py`, `d7a786e`) |

**Consequences an accurate v1 would have had to draw.**
- In the paper's terms, the baseline has "two copies of their `E` and none of their `S`"
  (§4 item 1, structural note).
- Two interchangeable L1 penalties competing for one residual make winner-takes-all the
  **expected** outcome. So the "collapse" is a property of that formulation, not a
  discovery about SS-RTD (§4 item 1; AB §4).
- The penalty-ramp difference is an independent **candidate** mechanism for the collapse
  (PN 13). It is not measured, and §6 item 4 adds a qualifier.

**For v2's baseline section.** List all four divergences, plus the stopping rule. A reader
can then check that the baseline is not "SS-RTD minus one term" (§2.1). The record calls it
"a different algorithm, not a partial implementation" (§1, resolution note).

### 2.4 Reference [5]: citation year

| field | v1 [5] | record | verdict |
|---|---|---|---|
| year | **2022** | **2023**: the issue year, Crossref `issued`/`published-print` 2023; IEEE style cites the issue (§29.1). OpenAlex's 2022 is the online year | **RETRACTED (§29.1)**. Change to 2023 |
| vol. / no. | 20, 1 | 20, 1 (`paper/SOURCE.md`) | consistent, but **not independently verified** (§29.1: "Not re-verified today: the volume and issue (20, 1) and pages (583-596)") |
| pages | 583–596 | 583–596, "**never** … checked against a source" (`ISSUE_VERSION_CHECKLIST.md` row 0.2) | **ORPHANED**. Check against Crossref before the bibliography is final (§29.1) |
| authors | B. Shen, R. R. Kamath, H. Choo, Z. Kong | `paper/SOURCE.md`: "Z. (James) Kong" | consistent; checklist row 0.1 confirms order against the issue version |
| title | as in `SOURCE.md` | — | SURVIVES |
| DOI | absent | 10.1109/TASE.2022.3163674 | add it. The `2022` in the DOI string is the assignment year, not the publication year (§29.1) |

Two related cautions follow from §29.2 and §30.1.

1. **Which version was verified.** Every v2 statement that the implementation was
   "verified against the paper" refers to the **early-access** PDF (pages 1–14). A reviewer
   will read the **issue** version, pp. 583–596.
2. **Provisional findings.** Until `ISSUE_VERSION_CHECKLIST.md` is completed, the four
   rigor findings are provisional: PN 1 (rank rule), PN 11 (eq. 12 against Appendix A),
   PN 14 (stopping rule) and PN 15 (PSNR formula).

---

## 3. The cross-cutting question: do v1's SS-RTD claims hold for the real SS-RTD?

v1's conclusions were attributed to SS-RTD. Relabelling them to the baseline fixes the
attribution. It leaves open whether any of them happens to be **true of the real method**
as well. The record answers part of this.

| v1 claim, read as a claim about real SS-RTD | what the record shows | verdict as an SS-RTD claim |
|---|---|---|
| the three components collapse to two; one foreground component is empty | No per-run nonzero-% measurement exists for real SS-RTD on v1's metric (`|x| > 1e-6`), except `video_01`, where `E` is 78.9% nonzero (§7.8). At threshold 0.05 both `S` and `E` are non-empty at every λ on every video (§20.1), except `S` annihilation: 1/20 videos at λ 0.8 and 3/20 at λ 1.0 (§20.3). The record's finding is the opposite of separation-by-emptiness: the supports **coincide** far above chance (§19.1) | **ORPHANED†** on v1's metric. The one measured video contradicts it. The like-for-like comparison is gap I.4 in `MANUSCRIPT_NUMBERS.md` |
| the winner is decided by the parameter ratio, not the scene | SS-RTD has one parameter, so no ratio exists. λ moves the **level** of S/E coincidence (29.4x → 55.0x), but the **scene** decides the ordering (rank ρ +0.93 to +0.99 against the λ 0.4 ordering) and the dose-response (§20.1, §20.4) | **RETRACTED for SS-RTD** by construction (`paper/SOURCE.md`) and by §20.4, where the scene matters |
| the third component captures nothing distinct | `E` is a **misfit sink**: it claims `S`'s support far above chance (180/180, §19.1), and it takes over what `S` gives up as λ rises (§20.2) | **SUPERSEDED** by §19 and §23.1. Not "nothing": the wrong thing |

This contrast is what v2's baseline-comparison section exists to show (`V2_STRUCTURE.md`,
§VII). It has **not yet been measured head to head** (gaps I.4 and I.6).

---

## 4. Title, front matter and references

| item | v1 text | verdict | basis and corrected version |
|---|---|---|---|
| Title | "Component collapse in Three-Component Tensor Decomposition for Surveillance Video Compression: An Empirical Study On VIRAT" | **SUPERSEDED** (§23.1) | "Component collapse" is the baseline's property (§4 item 1). The contribution is the misfit sink in a model class (§23.1). Compression is no longer a research question (`V2_STRUCTURE.md`). The title must name the finding, not the collapse, and not lead with compression |
| Abstract, index terms | absent from this PDF | — | required for IEEE Access. New in v2 |
| Author block | name, affiliation, e-mail | not a claim | — |
| [1] Do et al., *Appl. Sci.* 15(14) 8089, 2025 | | **ORPHANED** | never checked by `src/verify_refs.py` (§29.1 records only [5]). Run the DOI pass on every reference |
| [2] Statista, accessed 2025-03-27 | | **ORPHANED** | web source, not verified. It carries the 80%-of-traffic figure (§5, §I) |
| [3] Candès et al., *J. ACM* 58(3), 2011 | | **ORPHANED** | not checked |
| [4] Lu et al., CVPR 2016 | | **ORPHANED** | not checked |
| [5] Shen et al. | | see §2.4 | year → 2023; pages unverified; add the DOI |
| [6] Yu and Yang, *Pattern Recognit.* 137, 109343, 2023 | | **ORPHANED** | not checked. It carries two of v1's literature claims (§5, §I ¶3–4) |
| [7] Chen et al., ACM MM 2012 | | **ORPHANED** | not checked |
| reference count (7) | | **SURVIVES as a criticism** | reviewer minor point: "Sparse related-work section (7 references)" (§2). `AI_DISCLOSURE_FACTS.md` §5: no reference has been chosen by the agent, so the bibliography is the author's to expand |

---

## 5. Section by section

### §I Introduction (p.1)

| ¶ | quoted claim | verdict | basis and corrected version |
|---|---|---|---|
| 1 | "The data volume from surveillance cameras is still a significant challenge … [1]" | ORPHANED | motivation; [1] unverified |
| 1 | "video accounted for over 80% of global internet traffic in 2023 … [2]" | ORPHANED | [2] unverified. If kept, check the figure against the source |
| 1 | "much of the surveillance video data is redundant and static background" | ORPHANED | plausible. The record's `box_occupancy` (median 1.490%, G2) supports "mostly background" on VIRAT specifically |
| 2 | "RPCA-family decomposition helps to compress surveillance video efficiently" | **ORPHANED†** | v1's own Table III contradicts it for the hybrid (0/180, AB §4). Only `L` alone is smaller, and that comparison is flagged as unfair (§2 Major 3) |
| 2 | "It evolved: matrix form to tensor form to three-component form … [4] … [5]" | SURVIVES (background) | narrative of [3]→[4]→[5]; the references are unverified |
| 2 | "three-component forms such as SS-RTD add a third term to capture noise or residual [5]" | SURVIVES, correct | "noise", not "residual" (§2.2 #1) |
| 3 | "The technique was first introduced by Robust PCA (RPCA) [3]" | ORPHANED (phrasing) | reviewer minor point: RPCA used as both technique and origin (§2) |
| 3 | "researchers added a third component and noted that these are sensitive to trade-off parameters [6]" | ORPHANED | [6] unverified. Note that the source paper claims the opposite for SS-RTD (single λ, flat performance across [0.2, 1], Fig. 4) |
| 3 | "RPCA decomposition has been applied specifically to surveillance video compression [7]" | ORPHANED | [7] unverified |
| 4 | "SS-RTD was designed and validated on X-ray imaging data, where foreground is smooth" | **ORPHANED†** [audit] | the source paper's validation (§IV) is on SBI Candela, Caviar1 and Caviar2 (walking people "treated as the smooth foreground") and CDnet Highway, Office and Pedestrians, with 10–30% impulse noise. X-ray AM is §V and the motivation. Corrected: "designed for noisy X-ray video of metal additive manufacturing and validated on surveillance and traffic benchmark clips with synthetic impulse noise". See §6 item 1; `RESEARCH_LOG.md` §32.1 |
| 4 | "These methods also depend heavily on trade-off parameters that are difficult to set reliably [6]" | **SUPERSEDED** for SS-RTD (§20) | SS-RTD has one λ. §20 measured its effect: it moves the coincidence level (29.4x → 55.0x) but never its sign (96/96 runs above 1). The statement holds for the baseline (§3.2) |
| 4 | "Their behavior and sensitivity on surveillance video have not been systematically studied" | ORPHANED | a literature claim. Partly undercut by the source paper's own sensitivity study on Candela/Caviar (Fig. 4) |
| 4 | "whether the third component helps on compressing surveillance video is an open question" | SUPERSEDED (§23.1) | v2's question is what the third component **represents** when its designated signal is absent, not whether it helps compression |
| 5 | "a systematic empirical study on 180 VIRAT videos, running Tensor RPCA and SS-RTD" | **RELABEL** | Tensor RPCA and the naive baseline (§3.1; AB §3). In v2, real SS-RTD also ran on 180 (§19) |
| 5 | "its three-component decomposition systematically collapses to two … determined by the parameter values rather than by the video content" | **RELABEL** | true of the baseline (§3.1, §3.2; AB §4). §4 item 1: it is the expected consequence of two L1 terms, not a discovery |
| C1 | "in all 180 videos, the foreground is captured entirely by a single component while the other collapses to near zero" | **RELABEL** | baseline, 180/180 `N` (§3.1). Reviewer Major 4 and §4 item 3: the 180-video run used config_4, the most collapse-forcing setting, so this contribution is "partly *chosen*". It must merge with C2 |
| C2 | "The collapse winner is parameter-controlled … unanimous in every configuration (20/20) … equal penalties → S wins by tie-break" | **RELABEL** | baseline (§3.2). The tie-break is an **update-order artifact**: `S` is updated before `N` (`ssrtd.py:87-88`). It is deterministic (§3.3) |
| C3 | "Tensor RPCA's background component L beats H.264 by approximately 6.8% on 176/180 videos, but the hybrid … N does not beat H.264 on any video" | numbers **SURVIVE**; `N` **RELABEL** | recomputed: 176/180, mean 6.83%, range −0.60% to +18.08%; hybrid 0/180, 1.352x–1.873x, mean 1.551x. Both sides are CRF 28 (§6 item 2). Reviewer Major 3: the L-vs-H.264 comparison sets static background against full video (`START_HERE.md`, fix #2) |

### §II Methodology (pp.1–2)

| sub | quoted claim | verdict | basis and corrected version |
|---|---|---|---|
| A | "It decomposes the video using two tensor decomposition methods … analyzes how one method's decomposition parameters affect the result" | **RELABEL** | the two methods were Tensor RPCA and the baseline. v2 has three: Tensor RPCA, SS-RTD, baseline |
| B | grayscale; downsampled; normalized to a fixed range; stacked H×W×T | **SURVIVES** | `preprocessing.py:21-22` (INTER_AREA to 320×180, /255.0); §24.2 |
| B | "color adds no benefit and triples the data" | ORPHANED | "no benefit" is untested |
| B | normalization "so that … the decompositions behave consistently" | ORPHANED | rationale only |
| C | RPCA separates low-rank static background from sparse moving foreground; Tensor RPCA works on the tensor, giving `L`, `S` | **SURVIVES** | §1, `src/tensor_rpca.py` |
| C | "SS-RTD adds a third component N to capture noise or residual" | **RELABEL** | §2.2 #5 |
| C | "We use ADMM … to solve the convex optimization problems these decomposition methods pose" | **ORPHANED†** for SS-RTD | published SS-RTD fixes the Tucker rank of `L` (eq. 3, solved by HOOI, eq. 8; `paper/SOURCE.md`), which is a non-convex subproblem. Whether the baseline's averaged-SVT update solves a convex problem is not in the record. Say "solved by ADMM", without "convex" |
| C | "ADMM updates one component while holding the others fixed, then cycles … until the solution converges" | SURVIVES | generic. Note that real SS-RTD on VIRAT never met its tolerance; the 100-iteration cap is the effective stop (B17; PN 4) |
| C | the smoothness-penalty sentences | **RETRACTED** / SURVIVES in part | §2.1, rows 1–5 |
| D | H.264 per component; PSNR in dB; SSIM in [0, 1]; sparsity as near-zero fraction | SURVIVES as a description | `compression.py`, `metrics.py` |
| D | "We assess reconstruction fidelity using PSNR … SSIM" | **ORPHANED** (promised, never reported) | reviewer Major 2. The batch's `ssrtd_psnr`/`tensor_psnr` columns are tautological (~217 dB; §1; AB §3), so they could never have been reported. Valid: `hybrid_psnr`, median 30.70 dB (AB §3); real SS-RTD under noise, +20.35 dB median gain (F8) |
| E | "SS-RTD has trade-off parameters that control how strongly each component is penalized. These parameters directly determine which component holds the foreground" | **RELABEL** | baseline (§3.2). SS-RTD's λ weights the TV term only (§11) |
| E | "whether SS-RTD's behavior is controlled by the parameters or by the content of the video" | **RELABEL** | for the baseline, the parameters (§3.2). For real SS-RTD, both: λ sets the level, the scene sets the order (§20.4) |

**Figure 1** (p.2):
- Verdict: **RELABEL**.
- The "SS-RTD" box producing `L, S, N` is the baseline.
- The pipeline shape (preprocessing → decomposition → compression → parameter analysis)
  no longer matches the study, because compression is no longer a research question.
- v2 needs three decomposition branches with correct outputs:
  - SS-RTD → `L, S, E`;
  - baseline → `L, S, N`;
  - Tensor RPCA → `L, S`.
- "Parameter Analysis" becomes the λ sweep plus the noise condition (H, Fig. 1:
  "`S` = sparse **moving** term").

### §III Experiments (p.2)

| sub | quoted claim | verdict | basis and corrected version |
|---|---|---|---|
| A | videos-01 subset of VIRAT Ground 2.0, all 180 videos, official Kitware repository | **SURVIVES** | §3.1; `CLAUDE.md` Dataset; §24.1 (180/180 matched) |
| A | "All videos are 1280 × 720 and contain at least 300 frames" | **SURVIVES** | §24.1: uniform 1280×720, all 180, ≥300 frames, 23.97 fps |
| A | first 300 frames; grayscale; 320×180; [0, 1] | **SURVIVES** | §3.1; §24.2; `preprocessing.py:21-22` |
| A | "this cap is fixed before experimentation" | ORPHANED | the cap is recorded (initial `CLAUDE.md`), but when it was fixed relative to experimentation is not |
| B | "SS-RTD (Smooth Sparse Robust Tensor Decomposition)" | **RELABEL** | §2.2 #10 |
| B | Tensor RPCA "λ = 1/√max(H, W)" | **SURVIVES** | §1 (`tensor_rpca.py:66-67`, defaults used by `run_pipeline.py:90`) |
| B | "For SS-RTD, we use λs = 0.01 and λn = 0.001" | **RELABEL** | §1 (`run_pipeline.py:108`) |
| B | "Both methods are solved via ADMM with a maximum of 500 iterations and a convergence tolerance of 10⁻⁷" | **SURVIVES** for both methods as run (`ssrtd.py:46`; `tensor_rpca.py:70`) | state that the tolerance is on the relative change in `L`. The 180-video batch's iteration counts were never recorded (§4 item 1, "Blocker"). The sweep's were: 32 in all 100 runs (§6 item 4) |
| B | "We remove the smoothness penalty … float64 overflow" | **RETRACTED** | §2.1 |
| C | H.264 via ffmpeg; CRF 23 reference, CRF 28 compressed; components encoded separately; KB | **SURVIVES** | `compression.py:53-67`. v1 never says which CRF Table III uses (reviewer minor point). It is **CRF 28 on both sides** (§6 item 2) |
| C | "Reconstruction quality is assessed using PSNR and SSIM" | **ORPHANED** | as §II.D |
| C | "Sparsity … percentage of near-zero elements (|x| < 10⁻⁶)" | **SURVIVES** | `metrics.compute_sparsity` (§4 item 1, footnote on the 1e-6 threshold) |
| D | 20 videos × 5 configurations; four highest-density reserved, sixteen evenly spaced | **SURVIVES** as the baseline sweep design | §3.2; §8 (`select_videos`: 16 by rank plus the 4 busiest) |
| D | "They span the foreground-density range" | **SUPERSEDED** (§25.1; A1) | the statistic is a median-deviation **temporal-change** detector (`metrics.py:55`), not foreground amount: ρ +0.382 against annotated occupancy, Pearson −0.057. Describe it as "temporal change", with the numbers unchanged |
| D | the five (λs, λn) configurations | **RELABEL** | baseline (§3.2) |
| D | "we record … the reconstruction error" | ORPHANED (recorded, never reported) | `param_sweep.csv` `recon_error` is 1.15e-07 to 2.43e-07, which is the constraint residual (§3.2) |
| E | "implemented in Python 3.12 using NumPy, OpenCV, and ffmpeg" | ORPHANED for the 2026-06 baseline runs | no environment record exists for them. Phase 3 runs: Python 3.12.3, NumPy 2.4.6, SciPy 1.17.1, recorded per start (`results/metrics/ssrtd_real_manifest.json`) |
| E | "All code is publicly available at https://github.com/IlmunIslam/RPCA-Surveillance-Diagnostic" | SURVIVES (it is the `origin` remote) | ⚠️ the repository still contains the retracted docstring and the SS-RTD labels (§2.1, last bullet; §4 item 9) |

### Tables (p.3)

| table | content | verdict | basis and corrected version |
|---|---|---|---|
| **I** numbers | S nonzero % 0.02 / 0.147 / 0.56; N 99.87 / 99.945 / 99.99 | **SURVIVES** | recomputed exactly (means 0.1471 and 99.9454). The §IV.A text's "mean 99.95%" is the same value rounded. §3.1 quotes **medians** (0.10%, 99.95%), so say which statistic is meant |
| **I** caption | "The sparse component S collapses … while the residual component N holds almost all of the foreground" | **RELABEL**; "foreground" **ORPHANED** | the baseline's `S`/`N`. Nonzero-at-1e-6 cannot show that `N` holds the *foreground*: `N` is non-zero on 99.95% of voxels, which is essentially the whole residual X − L (§3.1: "N carries everything") |
| **II** numbers | 5 configs × 20/20 winners | **SURVIVES** | recomputed. Matches §3.2 |
| **II** order | rows 1, 3, 5, 2, 4 | SURVIVES as a criticism | reviewer minor point: out of numeric order and unexplained (§2) |
| **II** framing | stated as a separate finding from Table I | **RELABEL** + merge | baseline. Reviewer Major 4: Tables I and II show the same mechanism at two scales (`START_HERE.md`, fix #3) |
| **III** numbers | L 176/180, 6.8% smaller (mean); hybrid 0/180, 1.55x larger (mean) | **SURVIVES** | recomputed (`L_tensor_kb/original_comp_kb`; `hybrid_kb/original_comp_kb`). AB §4 confirms the hybrid figures |
| **III** labels | "Hybrid (L+N)" | **RELABEL** | `L` from Tensor RPCA plus `N` from the baseline (§3.1; AB §6) |
| **III** interpretation | "background component beats the H.264 baseline" | SURVIVES numerically; framing flagged | reviewer Major 3: static background against full video. Both encodes are CRF 28. Against the CRF-23 reference, `L` and even the hybrid are smaller on 180/180 (§6 item 2). State the CRF |

### §IV Results (p.3)

| sub | quoted claim | verdict | basis and corrected version |
|---|---|---|---|
| A | "At our batch parameter setting, in all 180 videos, the foreground goes entirely to N and S collapses" | **RELABEL** | baseline, `lam_s=0.01, lam_n=0.001`, 180/180 (§3.1). "Foreground goes to N" is v1's interpretation of nonzero-% (see Table I caption) |
| A | "S … max 0.56% nonzero, mean 0.147% … N … min 99.87%, mean 99.95%" | **SURVIVES** | recomputed |
| A | "None of the videos show any middle ground" | **SURVIVES** for the baseline | §3.1 |
| A | "This result holds across the full foreground-density range, 0.0127% to 4.263%" | numbers SURVIVE; naming **SUPERSEDED** (§25.1) | §3.1 (335x range). Say "temporal-change statistic", not "foreground density" |
| A | "The collapse is not limited to empty or busy scenes" | SURVIVES for the baseline; "empty/busy" SUPERSEDED (A1) | — |
| B | "In every configuration, there are no mixed outcomes … When λs < λn or λs = λn, S wins; when λs > λn, N wins" | **RELABEL** | baseline (§3.2, §3.3). The equality case is update order, not data (§3.2) |
| B | "The winner follows this parameter relationship over all densities" | RELABEL | — |
| B | (implicit) the transition is binary | ORPHANED | reviewer: no configuration near the boundary (e.g. 0.0011 vs 0.001) was tested (§2). Still untested |
| C | "On 176 out of 180 videos … L … is smaller than the H.264 baseline. The mean reduction is 6.8% … −0.60% … +18.08%" | **SURVIVES** | recomputed exactly. CRF 28 on both sides |
| C | "The hybrid combination (L+N) does not beat H.264 on any of the 180 videos … 1.35x to 1.87x … mean 1.55x" | **SURVIVES**; `N` **RELABEL** | AB §4; §4 item 8. The reviewer rates this the strongest result (§2) |

### §V Discussion (pp.3–4)

| sub | quoted claim | verdict | basis and corrected version |
|---|---|---|---|
| ¶0 | "The SS-RTD's three component decomposition collapses to two … depends on the set parameters, not the scene" | **RELABEL** | baseline |
| ¶0 | "The background of Tensor RPCA compresses better than H.264 but the hybrid does not" | SURVIVES (CRF 28) | Table III |
| A ¶1 | "SS-RTD is designed to capture smooth foreground in S and noise in N" | STAY, correct | "noise in `E`" (§2.2 #15) |
| A ¶1 | "the three component model (L+S+N) becomes two component model … The third component does not capture anything meaningfully distinct" | **RELABEL** | true of the baseline. As a claim about SS-RTD, SUPERSEDED (§3 of this file; §19; §23.1) |
| A ¶2 | "the winner is decided completely by which penalty (λs or λn) is smaller … The two foreground components are exchangeable. The component which is penalized less will absorb everything" | **SURVIVES** for the baseline | §3.2; AB §4: "a real property of the baseline method". §4 item 1 adds the reason: two interchangeable L1 terms. The reviewer notes the result is predictable from soft-thresholding (§2 Novelty), so present it as expected, not discovered |
| A ¶2 | "the split is not a discovery, it is an artifact" | SURVIVES | consistent with §4 items 1 and 3 |
| A ¶3 | "L compresses better than H.264 because it is temporally stable" | ORPHANED | no measurement of the mechanism. The reviewer calls the comparison close to tautological |
| A ¶3 | "The hybrid fails because surveillance foreground is not sparse, it is dense" | **ORPHANED†** | contradicted by the record's measures of scene content. `foreground_density` median 0.30% (§3.1) and annotated `box_occupancy` median 1.49% (§25.1), so the foreground is sparse. What is dense is the baseline's `N`, 99.95% non-zero (§3.1), because it absorbed the whole residual. The likely explanation is "`N` is dense", not "foreground is dense", and it is untested |
| B | "The collapse result … is specific to one setting (λs=0.01, λn=0.001). Because λs > λn, N wins every time" | **SURVIVES** for the baseline | §4 item 3, which says it more strongly: the setting was the most collapse-forcing one, so the unanimity is "partly *chosen*" |
| B | "The parameter sweep … partly mitigates this" | SURVIVES | §3.2 |
| B | "We've tested only VIRAT Ground 2.0 outdoor surveillance" | **SURVIVES** | still true for v2's VIRAT claims. The Candela gate (§6) is verification, not a second test domain |
| B | "full resolution or longer clips are untested … grayscale … 320×180 … 300 frames" | **SURVIVES** | still true. The reviewer adds that no sensitivity analysis on frames or resolution was done (§2, minor). Still none |
| B | "Our results for SS-RTD are without the smoothness term, we disabled it" | **RETRACTED** | §2.1 |
| B | "The original method might behave differently" | **SUPERSEDED** | §6 gate; §10–§27 |
| B | "The compression numbers are specific to H.264" | SURVIVES | — |
| C ¶1 | "The third component of SS-RTD does not give any meaningful separation … It either holds everything or holds nothing" | **RELABEL**; as an SS-RTD claim **SUPERSEDED** | §3 of this file |
| C ¶1 | "A simple two component based Tensor RPCA may give the same effective result with less complexity and computation" | ORPHANED | "effective result" is never measured. The runtime columns exist (`tensor_time_s`, `ssrtd_time_s`; AB §3) but were never compared |
| C ¶2 | "When two components fight for the same signal with only given penalty weight difference between them, the split becomes an artifact … check for this collapse" | **SURVIVES**, scoped | a correct lesson about **two interchangeable L1 terms** (§4 item 1). It must not be generalised to "three-component methods" without measurement (A20; reviewer Major 5) |
| C ¶3 | "The hybrid … does not beat a standard codec on dense foreground surveillance video" | numbers SURVIVE; "dense foreground" **ORPHANED†** | as A ¶3 |
| C ¶3 | "practitioners should focus on the background, not on splitting out foreground streams" | ORPHANED | reviewer Major 3: in surveillance the foreground is usually the information of interest |

### §VI Conclusion (p.4)

| quoted claim | verdict | basis and corrected version |
|---|---|---|
| "We've studied Tensor RPCA and SS-RTD on 180 surveillance videos" | **RELABEL** | §2.2 #19 |
| "We found SS-RTD's three component decomposition collapses to two on surveillance video" | **RELABEL** | baseline |
| "Which component wins is controlled by the parameters not the scene, so the third component is of no benefit" | **RELABEL** | baseline |
| future work: "test on more datasets and video types other than VIRAT" | SURVIVES | still open |
| future work: "examine whether other three component methods show the same behavior as SS-RTD" | **SUPERSEDED** | Phase 3 ran the published method. It behaves differently (§3 of this file). The open question v2 inherits is the reverse: does the misfit sink appear in other three-component models, including the baseline? (gap I.6; A20) |
| future work: "test other codecs such as H.265" | SURVIVES (open) | — |

---

## 6. Found during this audit [audit]

> **Recorded 2026-11-24 in `RESEARCH_LOG.md` §32** (items 1–4, re-checked there). Item 5
> is closed by the repository correction recorded in §4 item 9. Where this section and
> §32 differ, §32 is right.

1. **The source paper validates SS-RTD on surveillance-type video, not only X-ray.**
   Shen et al. §IV evaluates on SBI Candela, Caviar1 and Caviar2. Caviar1 has people
   "slowly walking along a corridor"; in Caviar2 people enter and leave a store. The
   walking people are "treated as the smooth foreground". §IV-C adds CDnet Highway
   (outdoor traffic), Office and Pedestrians. The injected impulse noise is 10–30%.
   X-ray AM data appears in §V and in the motivation. The project's gate (§6) itself runs
   on Candela.

   Consequence: "designed and validated for smooth X-ray foreground" overstates the
   domain gap. That wording appears in v1 §I ¶4, `CLAUDE.md`, `START_HERE.md`,
   `RESEARCH_PLAN.md` and §23.2. The difference between the source paper's experiments
   and this one is better described as:
   - 300 frames against 80;
   - **no noise** against 10–30% impulse noise (and real noise in the X-ray case).

   The last of these is the one the contribution turns on (§23.1: "when that noise is
   absent"). This strengthens the model-class framing and weakens the "X-ray → surveillance
   transfer" description of the experiment.
2. **Which CRF Table III uses, and why it matters.** Per `run_pipeline.py:193-194` and
   `compression.py:53-67`:
   - `original_comp_kb` is the original encoded at **CRF 28**;
   - `L_tensor_kb` and `hybrid_kb` are **CRF 28** too;
   - so "176/180" and "0/180" are both CRF-28-against-CRF-28.

   Against the CRF-23 reference (`original_ref_kb`), `L` is smaller on 180/180 (mean 47.8%
   smaller), and the hybrid is **also** smaller on 180/180 (mean 13.5%). Mixing the two
   settings reverses the hybrid result, so v2 must state the CRF explicitly. This is the
   reviewer's "CRF ambiguity" minor point, made concrete.
3. **`hybrid_compression_ratio` (median 0.4773) is the hybrid's own CRF-28/CRF-23 size
   ratio.** It is `compressed_kb / reference_kb` of the hybrid stream
   (`compression.py:80`), not hybrid against original. That explains the "median below 1"
   puzzle in §4 item 8 and AB §3. It still should not be quoted as a result, but the
   "unaudited denominator" flag can be closed.
4. **The baseline sweep ran 32 iterations in all 100 runs** (`param_sweep.csv` `n_iter`).
   At that point `mu = mu_0·1.5³¹ ≈ 3.5–3.8×10⁴`, below the 10⁶ cap, which would bind at
   iteration 40. So PN 13's "saturates after ~40 of 500 iterations" did not happen in the
   sweep.

   The final thresholds `lam/mu` are 2.6×10⁻⁸ to 2.9×10⁻⁷, below the 1e-6 sparsity cut,
   but they were at or above it for 23–28 of the 32 iterations (§32.3). The 180-video batch used the same code and tolerance, but its iteration counts
   remain unrecorded (§4 item 1, "Blocker"). PN 13 should be re-read with this column in
   hand before it reaches the Discussion. This item is arithmetic on a recorded column,
   not a measurement of the batch.
5. **The public repository repeats the retracted claim**: `src/ssrtd.py:48,55` and
   `README.md:12,35`. §4 item 9 already lists both as pending. Listed again here because v1
   points readers at that repository.

---

## 7. What carries forward, in one table

| v1 element | fate in v2 |
|---|---|
| dataset, preprocessing (§II.B, §III.A) | forward, nearly verbatim |
| Tensor RPCA description and λ | forward |
| 180-video "collapse" (Table I, §IV.A, C1) | **baseline comparison section**, relabelled, merged with the sweep |
| 20×5 sweep (Table II, §IV.B, C2) | **baseline comparison section**, merged with the above as one mechanism; tie-break stated as update order |
| hybrid compression (Table III, §IV.C, C3) | secondary result or appendix (author's decision; `V2_STRUCTURE.md`), with the CRF stated and the L-only claim reframed |
| smoothness-penalty paragraph, overflow, "disabled" | **deleted**. Replaced by the four-divergence account and the verification record. The retraction is addressed in the response letter |
| interpretation of the collapse (§V.A ¶2, §V.C ¶2) | forward as the **baseline's** mechanism, scoped to two interchangeable L1 terms |
| limitations (§V.B) | forward, except the retracted sentence, plus the new limitations (`V2_STRUCTURE.md`) |
| conclusions about SS-RTD (§V.C ¶1, §VI) | replaced by the misfit-sink result (§23.1) |
| references [1]–[7] | all re-verified; [5] year corrected; bibliography expanded |
