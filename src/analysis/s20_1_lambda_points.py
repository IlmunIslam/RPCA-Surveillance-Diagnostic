"""RESEARCH_LOG.md §20.1 -- the five lambda points (medians, ranges, rho vs fg, slopes).

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:36 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s20_1_lambda_points
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
groups=collections.defaultdict(dict)
for r in rows:
    if r['arm'] in ('clean-subset','lambda-sweep'):
        groups[float(r['lam'])][r['video_id']]=r
ids=sorted(groups[0.4])
hdr=(f"{'lam':>5s} {'S>.05%':>8s} {'E>.05%':>8s} {'S_px=0':>7s} {'P(E|S)%':>9s} "
     f"{'enrich med':>11s} {'range':>17s} {'>1':>8s} {'rho(fg)':>9s} {'p':>9s} {'slope':>7s}")
print(hdr); print('-'*len(hdr))
S={}
for lam in sorted(groups):
    g=groups[lam]
    s5=[fl(g[i],'S_gt005_pct') for i in ids]
    e5=[fl(g[i],'E_gt005_pct') for i in ids]
    zero=[i for i in ids if fl(g[i],'S_claimed_px')==0]
    defd=[i for i in ids if i not in zero]
    enr={i: fl(g[i],'SE_overlap_005')/fl(g[i],'E_gt005_pct') for i in defd}
    ov=[fl(g[i],'SE_overlap_005') for i in defd]
    fg=[fl(g[i],'foreground_density') for i in defd]
    ev=[enr[i] for i in defd]
    rs,ps=spearman(fg,ev)
    lx=[math.log(x) for x in fg]; ly=[math.log(y) for y in ev]
    mx,my=mean(lx),mean(ly)
    slope=sum((a-mx)*(b-my) for a,b in zip(lx,ly))/sum((a-mx)**2 for a in lx)
    S[lam]=dict(enr=enr, zero=zero, slope=slope, rho=rs, p=ps, med=median(ev))
    print(f"{lam:5.1f} {median(s5):8.3f} {median(e5):8.3f} {len(zero):7d} {median(ov):9.3f} "
          f"{median(ev):10.1f}x {min(ev):6.1f}-{max(ev):7.1f}x {len(ev):3d}/{len(ev):<4d} "
          f"{rs:+9.3f} {ps:9.2e} {slope:+7.3f}")
print()
print('videos where S claims ZERO pixels above 0.05 (enrichment undefined):')
for lam in sorted(groups):
    if S[lam]['zero']: print(f'  lam {lam}: {len(S[lam]["zero"])} -> {", ".join(S[lam]["zero"])}')
print()
print('--- per-video stability vs lam 0.4 (only videos defined at both) ---')
base=S[0.4]['enr']
for lam in sorted(groups):
    if lam==0.4: continue
    common=[i for i in base if i in S[lam]['enr']]
    rs,_=spearman([base[i] for i in common],[S[lam]['enr'][i] for i in common])
    rat=[S[lam]['enr'][i]/base[i] for i in common]
    print(f"lam {lam}: n={len(common):2d} rank rho {rs:+.3f}  ratio median {median(rat):.2f}x "
          f"({min(rat):.2f}-{max(rat):.2f})")
