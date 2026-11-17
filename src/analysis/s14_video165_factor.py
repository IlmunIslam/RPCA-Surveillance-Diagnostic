"""RESEARCH_LOG.md §14 (first factor2 row) -- video_165 at factor 1.0 vs 2.0.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-20 00:10 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 60 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 60 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s14_video165_factor
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 60


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
for f in ('1.0','2.0'):
    r=[x for x in rows if x['video_id']=='video_165' and x['condition']=='clean' and x['factor']==f]
    if not r: continue
    r=r[0]
    enr=float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
    print(f"factor {f}: S>.05 {float(r['S_gt005_pct']):.4f}%  E>.05 {float(r['E_gt005_pct']):.4f}%  "
          f"P(E|S) {float(r['SE_overlap_005']):.3f}%  enrich {enr:.1f}x  E!=0 {float(r['E_nonzero_pct']):.1f}%  "
          f"l1_E {float(r['l1_E']):.4g}  err_X {float(r['err_X_final']):.4g}")
