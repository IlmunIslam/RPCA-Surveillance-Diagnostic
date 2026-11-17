"""RESEARCH_LOG.md §19.1 (THE 180-VIDEO HEADLINE) -- the full 160-video clean-rest analysis and the 180-video pool.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-05 10:12 UTC. Added: this header and the working-directory lines.
Runs against the current results unchanged: its input has not changed since.

Run from the repo root:  python -m src.analysis.s19_1_clean_rest_full
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import spearman, pearson, median, sd
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv')))
def enr(r): return float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
def fg(r): return float(r['foreground_density'])
sub=[r for r in rows if r['arm']=='clean-subset']
rest=[r for r in rows if r['arm']=='clean-rest']
print('clean-subset n=%d | clean-rest n=%d' % (len(sub), len(rest)))
for name,g in (('subset (20)',sub),('rest (160)',rest)):
    e=[enr(r) for r in g]; f=[fg(r) for r in g]
    lf=[math.log(x) for x in f]; le=[math.log(x) for x in e]
    mx=sum(lf)/len(lf); my=sum(le)/len(le)
    sl=sum((a-mx)*(b-my) for a,b in zip(lf,le))/sum((a-mx)**2 for a in lf)
    r1,p1=spearman(f,e)
    print()
    print('%-12s median %6.1fx | range %5.1f - %6.1f | >1 on %d/%d' % (name, median(e), min(e), max(e), sum(1 for x in e if x>1), len(e)))
    print('%-12s fg span %.3f - %.3f%% (median %.3f)' % ('', min(f), max(f), median(f)))
    print('%-12s rho %+.3f (p~%.2e) | log-log slope %+.3f' % ('', r1, p1, sl))
print()
allc = sub+rest
e=[enr(r) for r in allc]; f=[fg(r) for r in allc]
print('POOLED all %d clean factor-1 videos: median %.1fx | range %.1f-%.1f | >1 on %d/%d' % (len(allc), median(e), min(e), max(e), sum(1 for x in e if x>1), len(e)))
print('  rho %+.3f (p~%.2e)' % spearman(f,e))
