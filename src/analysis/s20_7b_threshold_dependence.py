"""RESEARCH_LOG.md §20.7b -- enrichment level and raw P(E|S) at thresholds 0.01 vs 0.05.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:49 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s20_7b_threshold_dependence
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
import numpy as np, csv, collections
from pathlib import Path
from src.phase3_checkpoint import median, mean, sd, spearman
R=Path('results/ssrtd_real/runs')
def enr(run, thr):
    """enrichment and components at threshold thr ('001' or '005'), all voxels."""
    d=np.load(R/run/'supports.npz')
    n=int(np.prod(d['shape']))
    S=np.unpackbits(d[f'S_gt{thr}'])[:n].astype(bool)
    E=np.unpackbits(d[f'E_gt{thr}'])[:n].astype(bool)
    s,e=S.sum(),E.sum()
    if s==0 or e==0: return None
    both=np.count_nonzero(S&E)
    return dict(s=s/n*100, e=e/n*100, pes=both/s*100, enr=(both/s)/(e/n))
ids=[p.name.split('__')[0] for p in sorted(R.glob('*clean__f1__lam0.2__s0'))]
print(f'videos: {len(ids)}')
res=collections.defaultdict(dict)
for lam,tag in ((0.4,'lam0.4'),(1.0,'lam1')):
    for thr in ('001','005'):
        vals={}
        for v in ids:
            r=enr(f'{v}__clean__f1__{tag}__s0', thr)
            if r: vals[v]=r
        res[(lam,thr)]=vals
        print(f'lam {lam} thr 0.{thr[1:]}: n={len(vals):2d} median enrichment {median([x["enr"] for x in vals.values()]):7.1f}x '
              f'S {median([x["s"] for x in vals.values()]):7.4f}%  E {median([x["e"] for x in vals.values()]):7.4f}%  '
              f'P(E|S) {median([x["pes"] for x in vals.values()]):6.2f}%')
print()
print('=== DECISIVE CHECK: is the lam-slope of enrichment threshold-robust? ===')
for thr in ('001','005'):
    a,b=res[(0.4,thr)],res[(1.0,thr)]
    com=[v for v in a if v in b]
    rat=[b[v]['enr']/a[v]['enr'] for v in com]
    up=sum(1 for x in rat if x>1)
    print(f'  thr 0.{thr[1:]}: paired lam0.4->1.0 enrichment ratio median {median(rat):.3f}x '
          f'(n={len(com)}, {up}/{len(com)} up, range {min(rat):.2f}-{max(rat):.2f})')
print()
print('=== how much does a 5x THRESHOLD change move enrichment? (bounds the beta_X confound) ===')
for lam in (0.4,1.0):
    a,b=res[(lam,'001')],res[(lam,'005')]
    com=[v for v in a if v in b]
    rat=[b[v]['enr']/a[v]['enr'] for v in com]
    rawr=[b[v]['pes']/a[v]['pes'] for v in com]
    print(f'  lam {lam}: enrichment 0.01->0.05 ratio median {median(rat):.3f}x; '
          f'raw P(E|S) ratio median {median(rawr):.3f}x  '
          f'-> raw is {abs(median(rawr)-1)/max(abs(median(rat)-1),1e-9):.2f}x more threshold-sensitive')
