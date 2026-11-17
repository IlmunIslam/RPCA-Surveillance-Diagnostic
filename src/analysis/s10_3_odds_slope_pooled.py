"""RESEARCH_LOG.md §10.3 -- odds ratios, partials, log-log slope, pooled figure without video_01.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 12:20 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 20 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 20 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s10_3_odds_slope_pooled
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 20


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import spearman, pearson, _ranks, median
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
n=180*320*300
fg,S,enr,orat=[],[],[],[]
for r in rows:
    Sp=int(r['S_claimed_px']); both=int(r['SE_both_px']); E=float(r['E_gt005_pct'])/100*n
    fg.append(float(r['foreground_density'])); S.append(Sp)
    enr.append(both/(Sp*E/n))
    s_only=Sp-both; e_only=E-both; neither=n-Sp-E+both
    orat.append((both*neither)/(s_only*e_only))
def partial(x,y,z):
    rx,ry,rz=_ranks(x),_ranks(y),_ranks(z)
    rxy=pearson(rx,ry)[0]; rxz=pearson(rx,rz)[0]; ryz=pearson(ry,rz)[0]
    return (rxy-rxz*ryz)/math.sqrt((1-rxz**2)*(1-ryz**2))
print('odds ratio: median %.1f  min %.1f  max %.1f' % (median(orat), min(orat), max(orat)))
print('OR  vs fg_density      Spearman rho %+.3f (p~%.4f)' % spearman(fg,orat))
print('enr vs fg_density      Spearman rho %+.3f (p~%.4f)' % spearman(fg,enr))
print('enr vs fg | S_px       partial rho  %+.3f' % partial(fg,enr,S))
print('enr vs S_px | fg       partial rho  %+.3f' % partial(S,enr,fg))
print()
print('log-log fit enrichment ~ fg_density:')
lf=[math.log(x) for x in fg]; le=[math.log(x) for x in enr]
r,_=pearson(lf,le)
mx=sum(lf)/len(lf); my=sum(le)/len(le)
slope=sum((a-mx)*(b-my) for a,b in zip(lf,le))/sum((a-mx)**2 for a in lf)
print('  slope %.3f  (r %.3f) -> enrichment falls ~%.0f%% per 10x busier scene' % (slope, r, (1-10**slope)*100))
print()
print('contribution of video_01 to the pooled figure:')
v1=[r for r in rows if r['video_id']=='video_01'][0]
b1=int(v1['SE_both_px']); e1=int(v1['S_claimed_px'])*float(v1['E_gt005_pct'])/100
tb=sum(int(r['SE_both_px']) for r in rows)
te=sum(int(r['S_claimed_px'])*float(r['E_gt005_pct'])/100 for r in rows)
print('  video_01 = %.0f%% of overlapping voxels, %.0f%% of expected' % (b1/tb*100, e1/te*100))
print('  pooled WITHOUT video_01: %.1fx' % ((tb-b1)/(te-e1)))
