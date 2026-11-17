"""RESEARCH_LOG.md §15.1 (SUPERSEDED by §19) -- clean-rest at n=54 vs the subset.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-02 17:51 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 114 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 114 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s15_1_rest_vs_subset_n54
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
from src.phase3_checkpoint import spearman, pearson, median, _ranks
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
def enr(r): return float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
sub=[r for r in rows if r['arm']=='clean-subset']
rest=[r for r in rows if r['arm']=='clean-rest']
print('clean-subset n=%d | clean-rest n=%d' % (len(sub), len(rest)))
for name,g in (('subset',sub),('rest',rest)):
    e=[enr(r) for r in g]; f=[float(r['foreground_density']) for r in g]
    print()
    print('%-8s enrichment  median %7.1fx  range %6.1f - %7.1f  mean %7.1f' % (name, median(e), min(e), max(e), sum(e)/len(e)))
    print('%-8s fg_density  median %7.3f%%  range %6.3f - %7.3f' % (name, median(f), min(f), max(f)))
    print('%-8s >1 on %d/%d' % (name, sum(1 for x in e if x>1), len(e)))
    r,p=spearman(f,e); print('%-8s enrichment vs fg_density  rho %+.3f (p~%.5f)' % (name, r, p))
    lf=[math.log(x) for x in f]; le=[math.log(x) for x in e]
    mx=sum(lf)/len(lf); my=sum(le)/len(le)
    sl=sum((a-mx)*(b-my) for a,b in zip(lf,le))/sum((a-mx)**2 for a in lf)
    print('%-8s log-log slope %+.3f (r %+.3f)' % (name, sl, pearson(lf,le)[0]))
