"""RESEARCH_LOG.md §22.2 controls 1-2 -- corrupted-voxel enrichment and the beta_X confound at lambda 1.0.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-07 14:42 UTC. Only this header and the working-directory lines
were added, and the original's control-3 tail was cut: it crashed on a wrong noise-mask path
(the clean run has none) and controls 3-5 were rerun as s22_2_controls_3_5.py. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s22_2_controls_1_2
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
# 2026-11-19: the printed threshold labels are corrected (RESEARCH_LOG.md section 31.7).
# The mask keys '001'/'005' are thresholds 0.01/0.05, but the original printed them as
# 0.{thr} = '0.001'/'0.005'. Labels now print 0.{thr[1:]}. No computed value changes,
# and this is the only change to the original code.
import numpy as np, math, csv
from pathlib import Path
from src.phase3_checkpoint import median, mean, sd, spearman
R=Path('results/ssrtd_real/runs')
def parts(run, thr, pop):
    d=np.load(R/run/'supports.npz'); n=int(np.prod(d['shape']))
    S=np.unpackbits(d[f'S_gt{thr}'])[:n].astype(bool)
    E=np.unpackbits(d[f'E_gt{thr}'])[:n].astype(bool)
    m=np.load(R/run/'noise_mask.npz'); cor=np.unpackbits(m['mask'])[:n].astype(bool)
    keep={'unc':~cor,'cor':cor,'all':np.ones(n,bool)}[pop]
    S,E=S[keep],E[keep]; nn=int(keep.sum()); s,e=int(S.sum()),int(E.sum())
    if s==0 or e==0: return None
    return (int(np.count_nonzero(S&E))/s)/(e/nn)
ids=[p.name.split('__')[0] for p in sorted(R.glob('*clean__f1__lam0.2__s0'))]
print('CONTROL 1: enrichment on CORRUPTED voxels -- should stay ~1.0 at both lambda')
print('           (s12 measured 0.99x at lam0.4; E\'s noise work is independent of S)')
for lam,tag in ((0.4,'lam0.4'),(1.0,'lam1')):
    for thr in ('001','005'):
        v=[parts(f'{i}__impulse10__f1__{tag}__s0',thr,'cor') for i in ids]
        v=[x for x in v if x]
        print(f'  {tag} thr 0.{thr[1:]}: median {median(v):.3f}x  range {min(v):.3f}-{max(v):.3f}x  n={len(v)}')
print()
print('CONTROL 2: did the beta_X confound actually appear at lam 1.0?')
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv',newline='',encoding='utf-8')))
def grab(arm,lam):
    return {r['video_id']:float(r['beta_X_final']) for r in rows
            if r['arm']==arm and abs(float(r['lam'])-lam)<1e-9}
for lam,ca,na in ((0.4,'clean-subset','noise-subset'),(1.0,'lambda-sweep','noise-sweep')):
    c,n=grab(ca,lam),grab(na,lam)
    rat=[n[i]/c[i] for i in ids if i in c and i in n]
    print(f'  lam {lam}: beta_X noise/clean median {median(rat):.3f} '
          f'({min(rat):.3f}-{max(rat):.3f}) -> E threshold {1/median(rat):.2f}x higher under noise')
print()
