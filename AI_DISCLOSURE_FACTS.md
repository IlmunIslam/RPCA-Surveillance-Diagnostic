# AI DISCLOSURE: the factual content, from the record

> For the IEEE Acknowledgments disclosure (system, sections, level of involvement).
> Facts and structure only; the author writes the sentences. Compiled 2026-11-18 from
> git, the local Claude Code session transcript and the project record. Where the
> evidence runs out, this file says so instead of filling the gap.

## 1. The system

| fact | value | evidence |
|---|---|---|
| tool | **Claude Code** (Anthropic's agentic coding assistant, command-line interface), running on the author's laptop with file, shell and git access to the repository | session transcript |
| models, 2026-08-29 → 2026-11-17 | **`claude-opus-5`** (2,291 responses), then **`claude-opus-5-5`** (86 responses, the most recent stretch) | `model` field in transcript `f234d330…jsonl` |
| models, 2026-06-07 → 2026-07-07 | **unknown.** Claude Code sessions existed (memory files carry session IDs from 06-07 to 07-07), but no transcript is retained locally | `~/.claude/projects/S--works-Video-compression-Research/memory/` |
| what the model received | the contents of every file, command output and image the agent read: code, the record, CSV results, logs, rendered frames such as `decomposition_frame.png`, and material from the source paper. The raw VIRAT videos were processed locally by scripts | transcript tool calls |

## 2. What the evidence can and cannot attribute

- **Git cannot attribute anything.** All 88 commits are authored "Ilmun Islam" with no
  AI trailer, by the author's standing instruction. Of those, 63 date from
  2026-08-29 onward, and the transcript shows Claude Code issuing **41** `git commit`
  commands in that period. Authorship has to come from the transcript, not git.
- **The transcript covers 2026-08-29 → 2026-11-17 only**, which spans the whole pivot,
  Phase 1 and Phase 3.
- **The file tally below is a lower bound.** It counts the agent's direct file-write and
  file-edit tool calls. Some files were also written through shell or Python scripts
  (`RESEARCH_LOG.md` §25 and §26 among them), which the
  tally doesn't count.

## 3. Code

### 3a. Written by Claude Code (created by the agent, per the transcript)

| category | files | first written |
|---|---|---|
| **the solver**, real SS-RTD | `src/ssrtd_real.py` (+47 later edits) | 2026-09-09 |
| **unit tests**, 248 assertions, 7 suites | `src/test_tv_operators.py`, `test_hooi.py`, `test_s_update.py`, `test_f_update.py`, `test_e_update.py`, `test_multipliers.py`, `test_ssrtd_real.py` | 2026-09-09 → 09-13 |
| **verification gate** (Candela, Fig. 3 reproduction) | `src/gate_candela.py` | 2026-09-13 |
| diagnostic probes | `src/probe_relchg_L.py`, `src/probe_gate_fullspectrum.py` | 2026-09-19 |
| single-video measurement | `src/measure_virat_one.py` | 2026-09-18 |
| **Phase 3 batch infrastructure** | `src/phase3_runner.py`, `src/phase3_worker.py`, `src/phase3_checkpoint.py`, `watchdog_phase3.ps1`, `watchdog_system.ps1`, `install_watchdog_task.ps1` | 2026-10-17 → 10-20 |
| **analysis** | `src/prereg_s26_e_selectivity.py`; `src/analysis/` (31 scripts: 15 behind §20–§26 and 16 behind §9–§19, moved in from session scratch and the transcript on 2026-11-18; `RESEARCH_LOG.md` §28, §30.3) | 2026-11 |
| reference checking | `src/verify_refs.py` | 2026-11-18 |
| project configuration | `.claude/settings.json` (permission and deny rules) | 2026-09-19 |

Also edited by the agent: `src/tensor_rpca.py` (2 edits), `watchdog_param_sweep.ps1` (1).

~~⚠️ **The scratch analysis scripts are a disclosure and reproducibility gap.**~~ Closed
2026-11-18 for §20–§26: the scripts are in `src/analysis/`, each re-run and checked against its
recorded output (`RESEARCH_LOG.md` §28). ~~**Still open:** the inline analyses behind §9–§19
(including the 180-video headline, §19.1) are not yet in the repo (§28.4).~~ Closed
2026-11-18 for §9–§19 too: 16 scripts, all re-run and identical to their recorded output.
Where the results CSV has grown since a script ran, it is pinned to its row count at the time
(§30.3). Analyses from before the transcript (2026-08-29) remain unrecoverable.

### 3b. Pre-pivot code (2026-06-07 → 07-07): authorship not determinable from local evidence

`src/ssrtd.py` (the naive baseline), `tensor_rpca.py`, `preprocessing.py`,
`metrics.py`, `compression.py`, `hybrid_encoder.py`, `batch_runner.py`,
`run_pipeline.py`, `video_registry.py`, `param_sweep.py`, `download_annotations.py`,
`test_equal_lambda.py`. Claude Code sessions existed in this period (§1), but which
files they wrote is not recorded anywhere local. **Only the author can fill this
in**, and it matters: the original manuscript's mislabelling of the naive method as
"SS-RTD" (`RESEARCH_LOG.md` §4 item 1) dates from this period.

## 4. Figures and images

- **Manuscript figures: none made yet.** Each one should be logged here as it is made
  (the code that drew it, and who chose what it shows).
- Diagnostic images produced by agent-written code: `results/gate_candela/fig3_reproduction.png`,
  `decomposition_frame.png` (gate and `video_01`).

## 5. Text

| text | involvement | note |
|---|---|---|
| **manuscript prose** (Overleaf) | **none so far, with one exception** | the author writes it |
| ↳ exception: a ~315-word methodology paragraph on how the work corrected itself | **drafted by Claude Code at the author's request** (this session) | if any of it is used, even rewritten, it is AI-generated text and must be disclosed by section |
| the research record: `RESEARCH_LOG.md`, `PAPER_NOTES.md`, `START_HERE.md`, `PHASE3_NOTES.md`, `IMPLEMENTATION_PLAN.md`, `CLAUDE.md`, `MANUSCRIPT_NUMBERS.md` | **largely drafted by Claude Code**; reviewed, corrected and approved by the author before each commit | not manuscript text, but every manuscript number traces through it |
| `paper/SOURCE.md` (equation transcription) | read by the agent; authorship not in the tally | — |
| bibliography | **none.** No reference has been chosen by the agent; `verify_refs.py` checks references the author supplies | — |

## 6. Research decisions

**Taken by the author** (examples, each recorded where it happened):
- the pivot's framing and the model-class contribution (instruction 2026-10-20; `PAPER_NOTES.md` framing, §23)
- quote the enrichment ratio, not the raw overlap (2026-10-19; PAPER_NOTES item 18)
- the arm design: factor 2.0 as a robustness table, λ = 0.4, λ-sweep deferred until the subset landed (§8, §11)
- requiring pre-registration with confound analyses before data, and the three conditions for §26
- the withdrawal rule ("anything reported mid-arm that doesn't survive goes in the record as withdrawn")
- correcting the agent's diagnosis in §25.3 (superseded by §26.0); requiring the asymmetric-power statement in §26.7

**Proposed by Claude Code, approved or corrected by the author:** analysis designs,
statistics, confound bounds and pre-registration drafts (e.g. §26's statistic and its
reversed prediction); interpretations of results, several later withdrawn by the
agent itself (§20.7a, §25.4); the four source-paper inconsistencies (`PAPER_NOTES`
items 11, 14, 15; item 17 as inference). The project convention is that the author
reviews specs before code and results before commits (`CLAUDE.md`).

## 7. The verification regime that governed the AI-written code

| control | what it does | where |
|---|---|---|
| unit tests against the paper's equations | 248 assertions, 7 suites, machine-epsilon residuals | §7.7; PAPER_NOTES 7 |
| reproduction gate before any VIRAT run | reproduces Shen et al.'s Fig. 3 on their data (relErr_L 0.0137 vs ~0.013; iteration 1 0.0628 vs 0.0626) | §6 |
| bitwise gates on optimisations | every memory lever accepted only if it reproduced the reference bit for bit; the one non-exact change (half-spectrum FFT) accepted only after the finding was shown to survive it | §7.5–§7.8 |
| pre-registration | definitions, predictions and falsification boundaries committed before the data were computed (`63913fb`, `8339e2e`, `3b59daf`) | §21, §24, §26 |
| withdrawal rule | claims that fail at larger n or after de-confounding are recorded as withdrawn, not deleted | §12.2, §19.2, §20.7a, §25.4 |
| permission guards | deny rules stop the agent writing the frozen baseline CSVs; long runs and pushes need the author's approval at a prompt | `.claude/settings.json`; `ARCHIVE_BASELINE.md` §7 |
| author review | specs before code, results before commits; commit messages supplied by the author | `CLAUDE.md` |

The transcript also records a no-op guardrail probe on the frozen `all_results.csv`
(an edit of a non-existent string, 2026-10-19). It returned "string not found" and
changed nothing.
