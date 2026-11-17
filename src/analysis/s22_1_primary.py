"""RESEARCH_LOG.md §22.1 -- the pre-registered primary readout.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-07 14:41 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s22_1_primary
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import numpy as np, math
from pathlib import Path
from src.phase3_checkpoint import median, mean, sd
R=Path('results/ssrtd_real/runs')

def enrich(run, thr, uncorrupted_only):
    """Enrichment on the analysed voxel population. Returns None if S or E empty."""
    d=np.load(R/run/'supports.npz'); n=int(np.prod(d['shape']))
    S=np.unpackbits(d[f'S_gt{thr}'])[:n].astype(bool)
    E=np.unpackbits(d[f'E_gt{thr}'])[:n].astype(bool)
    if uncorrupted_only:
        m=np.load(R/run/'noise_mask.npz')
        keep=~np.unpackbits(m['mask'])[:n].astype(bool)
        S,E=S[keep],E[keep]; n=int(keep.sum())
    s,e=int(S.sum()),int(E.sum())
    if s==0 or e==0: return None
    both=int(np.count_nonzero(S&E))
    return dict(enr=(both/s)/(e/n), s=s/n*100, e=e/n*100, pes=both/s*100, n=n)

ids=[p.name.split('__')[0] for p in sorted(R.glob('*clean__f1__lam0.2__s0'))]
def sign_p(k,n): return min(1.0, 2*sum(math.comb(n,i) for i in range(k,n+1))/2**n)

for thr,label in (('001','PRIMARY  threshold 0.01'),('005','secondary threshold 0.05')):
    print(f'=== {label} ===')
    for cond,unc,tag in (('clean',False,'clean (all voxels)'),
                         ('impulse10',True,'impulse10 (UNCORRUPTED voxels only)')):
        a={}; b={}
        for v in ids:
            ra=enrich(f'{v}__{cond}__f1__lam0.4__s0', thr, unc)
            rb=enrich(f'{v}__{cond}__f1__lam1__s0',   thr, unc)
            if ra: a[v]=ra
            if rb: b[v]=rb
        com=[v for v in ids if v in a and v in b]
        rat=[b[v]['enr']/a[v]['enr'] for v in com]
        lr=[math.log(x) for x in rat]
        up=sum(1 for x in rat if x>1); nn=len(rat)
        sem=sd(lr)/math.sqrt(nn)
        print(f'  {tag}')
        print(f'    lam0.4 median enrichment {median([a[v]["enr"] for v in com]):8.2f}x   '
              f'lam1.0 median {median([b[v]["enr"] for v in com]):8.2f}x')
        print(f'    PAIRED ratio: median {median(rat):.3f}x  geo-mean {math.exp(mean(lr)):.3f}x  '
              f'95% CI {math.exp(mean(lr)-1.96*sem):.3f}-{math.exp(mean(lr)+1.96*sem):.3f}x')
        print(f'    {up}/{nn} rising   sign-test p = {sign_p(up,nn):.2e}   '
              f'(dropped {len(ids)-nn} for empty S or E)')
    print()
