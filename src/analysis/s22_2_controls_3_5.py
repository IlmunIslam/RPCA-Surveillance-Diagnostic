"""RESEARCH_LOG.md §22.2 controls 3-5 and §22.3 -- rank agreement, annihilation, and the level comparison.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-07 14:43 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s22_2_controls_3_5
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import numpy as np
from pathlib import Path
from src.phase3_checkpoint import median, spearman
R=Path('results/ssrtd_real/runs')
def parts(run, thr, pop):
    d=np.load(R/run/'supports.npz'); n=int(np.prod(d['shape']))
    S=np.unpackbits(d[f'S_gt{thr}'])[:n].astype(bool)
    E=np.unpackbits(d[f'E_gt{thr}'])[:n].astype(bool)
    if pop!='all':
        m=np.load(R/run/'noise_mask.npz'); cor=np.unpackbits(m['mask'])[:n].astype(bool)
        keep=cor if pop=='cor' else ~cor
        S,E=S[keep],E[keep]; n=int(keep.sum())
    s,e=int(S.sum()),int(E.sum())
    if s==0 or e==0: return None
    return (int(np.count_nonzero(S&E))/s)/(e/n)
ids=[p.name.split('__')[0] for p in sorted(R.glob('*clean__f1__lam0.2__s0'))]
print('CONTROL 3: do the SAME videos rise by the same amount in both conditions?')
for thr in ('001','005'):
    cr,nr=[],[]
    for i in ids:
        a=parts(f'{i}__clean__f1__lam0.4__s0',thr,'all'); b=parts(f'{i}__clean__f1__lam1__s0',thr,'all')
        c=parts(f'{i}__impulse10__f1__lam0.4__s0',thr,'unc'); d=parts(f'{i}__impulse10__f1__lam1__s0',thr,'unc')
        if a and b and c and d: cr.append(b/a); nr.append(d/c)
    rs,ps=spearman(cr,nr)
    print(f'  thr 0.{thr}: n={len(cr)}  rank rho between clean and noise lambda-ratios {rs:+.3f} (p~{ps:.4f})')
print()
print('CONTROL 4: annihilation at lam 1.0, thr 0.05')
for cond,pop,lbl in (('clean','all','clean (all voxels)'),('impulse10','unc','noise (uncorrupted)')):
    z=[i for i in ids if parts(f'{i}__{cond}__f1__lam1__s0','005',pop) is None]
    print(f'  {lbl:22s}: {len(z)} annihilated -> {", ".join(z) if z else "none"}')
print()
print('CONTROL 5: the LEVEL at lam 1.0 (s12 did this at lam 0.4: 40.4 clean vs 41.9 noise)')
for thr in ('001','005'):
    for lam in ('lam0.4','lam1'):
        c=[parts(f'{i}__clean__f1__{lam}__s0',thr,'all') for i in ids]
        n=[parts(f'{i}__impulse10__f1__{lam}__s0',thr,'unc') for i in ids]
        pair=[(a,b) for a,b in zip(c,n) if a and b]
        rs,_=spearman([a for a,b in pair],[b for a,b in pair])
        print(f'  thr 0.{thr} {lam:7s}: clean median {median([a for a,b in pair]):7.2f}x  '
              f'noise median {median([b for a,b in pair]):7.2f}x  rank rho {rs:+.3f}  n={len(pair)}')
