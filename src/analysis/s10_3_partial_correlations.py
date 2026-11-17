"""RESEARCH_LOG.md §10.3, run at the 10-VIDEO point (the arm was half done) -- partial correlations: scene content vs support size.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 08:27 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 10 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 10 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Note: this ran on the first 10 clean-subset videos, not the 20 that §10 reports. Only one
number from it reached the record: §10.3's fg vs S_px rho +0.818, which is +0.976 at
n=20 (§30.3). §10.3's other numbers come from s10_3_odds_slope_pooled (n=20).

Run from the repo root:  python -m src.analysis.s10_3_partial_correlations
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 10


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import spearman, _ranks, pearson
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
n=180*320*300
fg,S,enr=[],[],[]
for r in rows:
    Sp=int(r['S_claimed_px']); both=int(r['SE_both_px']); E=float(r['E_gt005_pct'])/100*n
    fg.append(float(r['foreground_density'])); S.append(Sp); enr.append(both/(Sp*E/n))

def partial(x,y,z):
    'Spearman partial corr of x,y controlling z'
    rx,ry,rz=_ranks(x),_ranks(y),_ranks(z)
    rxy=pearson(rx,ry)[0]; rxz=pearson(rx,rz)[0]; ryz=pearson(ry,rz)[0]
    return (rxy-rxz*ryz)/math.sqrt((1-rxz**2)*(1-ryz**2))

print('enrichment vs fg_density, controlling for S_px   partial rho %+.3f' % partial(fg,enr,S))
print('enrichment vs S_px, controlling for fg_density   partial rho %+.3f' % partial(S,enr,fg))
