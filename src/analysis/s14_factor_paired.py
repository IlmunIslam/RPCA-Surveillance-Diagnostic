"""RESEARCH_LOG.md §14.1-§14.2 -- paired factor 1.0 vs 2.0 across all 20 videos.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-22 05:04 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 60 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 60 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s14_factor_paired
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
from src.phase3_checkpoint import spearman, median
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
f1={r['video_id']:r for r in rows if r['condition']=='clean' and float(r['factor'])==1.0}
f2={r['video_id']:r for r in rows if r['condition']=='clean' and float(r['factor'])==2.0}
vids=sorted(set(f1)&set(f2), key=lambda v: float(f1[v]['foreground_density']))
print('paired videos:', len(vids))
print()
print(f"{'video':11s} {'fg%':>6s} {'enr_f1':>8s} {'enr_f2':>8s} {'d_enr':>7s} {'raw_f1':>7s} {'raw_f2':>7s} {'d_raw':>7s} {'Eocc_f1':>8s} {'Eocc_f2':>8s}")
e1l,e2l,dr,de=[],[],[],[]
for v in vids:
    a,b=f1[v],f2[v]
    r1,r2=float(a['SE_overlap_005']),float(b['SE_overlap_005'])
    o1,o2=float(a['E_gt005_pct']),float(b['E_gt005_pct'])
    x1,x2=r1/o1,r2/o2
    print(f'{v:11s} {float(a["foreground_density"]):6.3f} {x1:8.1f} {x2:8.1f} {(x2/x1-1)*100:+6.1f}% {r1:7.2f} {r2:7.2f} {(r2/r1-1)*100:+6.1f}% {o1:8.3f} {o2:8.3f}')
    e1l.append(x1); e2l.append(x2); dr.append(abs(r2/r1-1)*100); de.append(abs(x2/x1-1)*100)
print()
print('median enrichment  f1 %.1fx -> f2 %.1fx' % (median(e1l), median(e2l)))
print('enrichment f1 vs f2  Spearman rho %+.3f (p~%.5f)' % spearman(e1l,e2l))
print('enrichment > 1 at f2: %d/%d' % (sum(1 for x in e2l if x>1), len(e2l)))
print()
print('PAIRED SENSITIVITY to doubling the E threshold (median |relative change|):')
print('  raw P(E|S)   %6.1f%%' % median(dr))
print('  enrichment   %6.1f%%' % median(de))
print('  ratio        %.2fx less sensitive' % (median(dr)/median(de)))
