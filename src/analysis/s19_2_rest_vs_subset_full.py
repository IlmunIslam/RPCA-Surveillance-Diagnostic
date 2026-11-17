"""RESEARCH_LOG.md §19.2 -- subset vs rest at full n, and the extreme.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-05 10:12 UTC. Added: this header and the working-directory lines.
Runs against the current results unchanged: its input has not changed since.

Run from the repo root:  python -m src.analysis.s19_2_rest_vs_subset_full
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import spearman, median
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv')))
def enr(r): return float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
def fg(r): return float(r['foreground_density'])
sub=[r for r in rows if r['arm']=='clean-subset']
rest=[r for r in rows if r['arm']=='clean-rest']
lo,hi=min(fg(r) for r in rest), max(fg(r) for r in rest)
s2=[r for r in sub if lo<=fg(r)<=hi]
e1=[enr(r) for r in s2]; e2=[enr(r) for r in rest]
print('common density band %.3f-%.3f%%' % (lo,hi))
print('  subset within band n=%2d median %6.1fx' % (len(e1), median(e1)))
print('  rest              n=%d median %6.1fx' % (len(e2), median(e2)))
allv=sorted(e1+e2); n1,n2=len(e1),len(e2)
R1=sum(sorted(allv).index(x)+1 for x in e1)
U=R1-n1*(n1+1)/2; mu=n1*n2/2; sdv=math.sqrt(n1*n2*(n1+n2+1)/12); z=(U-mu)/sdv
p=2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2))))
print('  Mann-Whitney z=%+.2f p~%.3f -> %s' % (z,p,'no detectable difference' if abs(z)<1.96 else 'different'))
print()
print('top 3 enrichment in clean-rest:')
for r in sorted(rest,key=enr,reverse=True)[:3]:
    print('   %-11s fg %6.3f%%  enr %6.1fx  S_px %7s  both %6s  E>.05 %.4f%%' % (r['video_id'],fg(r),enr(r),r['S_claimed_px'],r['SE_both_px'],float(r['E_gt005_pct'])))
