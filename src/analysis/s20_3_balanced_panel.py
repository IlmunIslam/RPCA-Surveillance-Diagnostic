"""RESEARCH_LOG.md §20.2-§20.3 -- the 17-video balanced panel and paired ratios vs lambda 0.4.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:36 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s20_3_balanced_panel
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, collections, math
from src.phase3_checkpoint import median, mean, spearman
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv',newline='',encoding='utf-8')))
def fl(r,k):
    v=(r.get(k) or '').strip()
    try: return float(v)
    except: return None
g=collections.defaultdict(dict)
for r in rows:
    if r['arm'] in ('clean-subset','lambda-sweep'): g[float(r['lam'])][r['video_id']]=r
lams=sorted(g)
# balanced panel: defined at every lam
panel=[i for i in g[0.4] if all(fl(g[l][i],'S_claimed_px') for l in lams)]
print(f'balanced panel (S nonempty at all 5 lam): n={len(panel)}')
print()
print(f"{'lam':>5s} {'enrich med':>11s} {'P(E|S)% med':>12s} {'S_px med':>10s} {'E>.05% med':>11s} {'S+E claimed px':>15s}")
print('-'*70)
first={}
for l in lams:
    e=[fl(g[l][i],'SE_overlap_005')/fl(g[l][i],'E_gt005_pct') for i in panel]
    ov=[fl(g[l][i],'SE_overlap_005') for i in panel]
    spx=[fl(g[l][i],'S_claimed_px') for i in panel]
    e5=[fl(g[l][i],'E_gt005_pct') for i in panel]
    tot=[fl(g[l][i],'S_claimed_px')+fl(g[l][i],'E_gt005_pct')/100*17280000 for i in panel]
    first[l]=(median(e),median(ov))
    print(f"{l:5.1f} {median(e):10.1f}x {median(ov):12.2f} {median(spx):10.0f} {median(e5):11.3f} {median(tot):15,.0f}")
e0,o0=first[0.2]; e1,o1=first[1.0]
print()
print(f'across lam 0.2 -> 1.0 on the SAME {len(panel)} videos:')
print(f'  enrichment      {e0:.1f}x -> {e1:.1f}x   = {e1/e0:.2f}x change')
print(f'  raw P(E|S)      {o0:.2f}% -> {o1:.2f}%  = {o1/o0:.2f}x change')
print(f'  ratio of sensitivities: raw is {(o1/o0)/(e1/e0):.2f}x more lam-sensitive than enrichment')
# per-video paired, panel only
print()
for l in lams:
    if l==0.4: continue
    rat=[(fl(g[l][i],'SE_overlap_005')/fl(g[l][i],'E_gt005_pct'))/
         (fl(g[0.4][i],'SE_overlap_005')/fl(g[0.4][i],'E_gt005_pct')) for i in panel]
    up=sum(1 for x in rat if x>1)
    print(f'  lam {l} vs 0.4 (paired, n={len(panel)}): median {median(rat):.2f}x, {up}/{len(panel)} videos move up')
