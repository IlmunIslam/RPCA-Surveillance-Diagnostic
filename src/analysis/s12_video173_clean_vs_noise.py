"""RESEARCH_LOG.md §12 (first noise rows) -- video_173 clean vs impulse10.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 14:22 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 40 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 40 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s12_video173_clean_vs_noise
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 40


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
n=180*320*300
for cond in ('clean','impulse10'):
    r=[x for x in rows if x['video_id']=='video_173' and x['condition']==cond][0]
    e5=float(r['E_gt005_pct'])/100*n
    print(f"{cond:10s} E>.05 {e5:9.0f} px ({float(r['E_gt005_pct']):6.3f}%)  E!=0 {r['E_nonzero_pct']:>7s}%  "
          f"SE_ovl {r['SE_overlap_005']:>7s}%  prec005 {r['E_precision_005'] or '--':>8s}  rec005 {r['E_recall_005'] or '--':>8s}")
