"""RESEARCH_LOG.md §15.2 (SUPERSEDED by §19) -- both groups within a common density band, n=54.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-02 17:51 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 114 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 114 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s15_2_density_band_n54
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 114


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import spearman, pearson, median
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
def enr(r): return float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
def fg(r): return float(r['foreground_density'])
sub=[r for r in rows if r['arm']=='clean-subset']
rest=[r for r in rows if r['arm']=='clean-rest']
lo,hi=min(fg(r) for r in rest), max(fg(r) for r in rest)
print('restricting BOTH groups to the rest arm density band %.3f-%.3f%%' % (lo,hi))
s2=[r for r in sub if lo<=fg(r)<=hi]; r2=[r for r in rest]
for name,g in (('subset',s2),('rest',r2)):
    e=[enr(r) for r in g]
    print('  %-7s n=%2d  median %6.1fx  range %5.1f-%6.1f' % (name,len(g),median(e),min(e),max(e)))
# rank-sum test (Mann-Whitney U, normal approx) on the restricted comparison
e1=[enr(r) for r in s2]; e2=[enr(r) for r in r2]
allv=sorted(e1+e2); 
def rank(x): return allv.index(x)+1
R1=sum(rank(x) for x in e1); n1,n2=len(e1),len(e2)
U=R1-n1*(n1+1)/2; mu=n1*n2/2; sd=math.sqrt(n1*n2*(n1+n2+1)/12)
z=(U-mu)/sd
print('  Mann-Whitney z=%+.2f (p~%.3f) -> %s' % (z, 2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2)))), 'no detectable difference' if abs(z)<1.96 else 'DIFFERENT'))
print()
print('pooled all 74 clean factor-1 videos:')
e=[enr(r) for r in sub+rest]; f=[fg(r) for r in sub+rest]
print('  median %.1fx  range %.1f-%.1f  >1 on %d/%d' % (median(e),min(e),max(e),sum(1 for x in e if x>1),len(e)))
print('  enrichment vs fg_density  rho %+.3f (p~%.6f)' % spearman(f,e))
