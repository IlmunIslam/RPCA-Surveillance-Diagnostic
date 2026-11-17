"""RESEARCH_LOG.md §20.7a -- per-video transfer coefficient tau by lambda segment.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:46 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s20_7a_transfer_tau
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, collections
from src.phase3_checkpoint import median, mean, sd
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv',newline='',encoding='utf-8')))
def fl(r,k):
    v=(r.get(k) or '').strip()
    try: return float(v)
    except: return None
g=collections.defaultdict(dict)
for r in rows:
    if r['arm'] in ('clean-subset','lambda-sweep'): g[float(r['lam'])][r['video_id']]=r
ids=sorted(g[0.4]); lams=sorted(g)
print('CLEAN: per-video transfer tau = dE_rate / (-dS_rate), by lambda segment')
print(f"{'segment':>12s} {'tau med':>9s} {'tau mean':>9s} {'sd':>7s} {'range':>16s} {'tau in[.7,1.3]':>15s} {'dS_rate med':>12s}")
print('-'*90)
segs=[(0.2,0.4),(0.4,0.6),(0.4,0.8),(0.4,1.0),(0.2,1.0)]
store={}
for a,b in segs:
    taus=[]; dss=[]
    for i in ids:
        sa,sb=fl(g[a][i],'S_gt005_pct'),fl(g[b][i],'S_gt005_pct')
        ea,eb=fl(g[a][i],'E_gt005_pct'),fl(g[b][i],'E_gt005_pct')
        if sa is None or sb is None: continue
        ds=sa-sb
        if ds<=0: continue
        taus.append((eb-ea)/ds); dss.append(ds)
    store[(a,b)]=taus
    inb=sum(1 for x in taus if 0.7<=x<=1.3)
    print(f"{f'{a}->{b}':>12s} {median(taus):9.3f} {mean(taus):9.3f} {sd(taus):7.3f} "
          f"{min(taus):6.2f}-{max(taus):6.2f} {inb:9d}/{len(taus):<5d} {median(dss):12.4f}")
print()
print('precision: sem of median-ish (sd/sqrt(n)) -> smallest detectable fractional change at 20 videos')
for k,v in store.items():
    semfrac = (sd(v)/len(v)**0.5)/abs(mean(v))
    print(f"  {k[0]}->{k[1]}: n={len(v):2d} mean tau {mean(v):.3f}, sem {sd(v)/len(v)**0.5:.3f} "
          f"= {semfrac*100:4.1f}% of mean -> 2-sigma detectable shift ~{2*semfrac*100:.0f}%")
print()
print('annihilation risk by lambda (clean): videos with S_claimed_px == 0')
for l in lams:
    z=[i for i in ids if fl(g[l][i],'S_claimed_px')==0]
    near=[i for i in ids if fl(g[l][i],'S_claimed_px') and fl(g[l][i],'S_claimed_px')<2000]
    print(f'  lam {l}: zero {len(z):2d}  under-2000-voxels {len(near):2d}')
