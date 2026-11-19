"""RESEARCH_LOG.md §21.2 -- the clean lambda-slope at both thresholds, CIs and sign-test power.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:50 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s21_2_slope_threshold_robustness
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
import numpy as np, collections, math
from pathlib import Path
from src.phase3_checkpoint import median, mean, sd
R=Path('results/ssrtd_real/runs')
def enr(run, thr):
    d=np.load(R/run/'supports.npz'); n=int(np.prod(d['shape']))
    S=np.unpackbits(d[f'S_gt{thr}'])[:n].astype(bool)
    E=np.unpackbits(d[f'E_gt{thr}'])[:n].astype(bool)
    s,e=S.sum(),E.sum()
    if s==0 or e==0: return None
    return (np.count_nonzero(S&E)/s)/(e/n)
ids=[p.name.split('__')[0] for p in sorted(R.glob('*clean__f1__lam0.2__s0'))]
print('CLEAN paired lam0.4 -> lam1.0 enrichment ratio, per video:')
for thr in ('001','005'):
    rat=[]
    for v in ids:
        a=enr(f'{v}__clean__f1__lam0.4__s0',thr); b=enr(f'{v}__clean__f1__lam1__s0',thr)
        if a and b: rat.append(b/a)
    lr=[math.log(x) for x in rat]
    up=sum(1 for x in rat if x>1)
    # sign test p under H0: p=0.5
    n=len(rat); k=up
    p=2*sum(math.comb(n,i) for i in range(k,n+1))/2**n
    print(f'  thr 0.{thr[1:]}: n={n:2d} median {median(rat):.3f}x  geom-mean {math.exp(mean(lr)):.3f}x  '
          f'sd(log) {sd(lr):.3f}  {up}/{n} up  sign-test p={min(p,1):.2e}')
    sem=sd(lr)/math.sqrt(n)
    print(f'            95% CI on geometric mean: '
          f'{math.exp(mean(lr)-1.96*sem):.3f}x - {math.exp(mean(lr)+1.96*sem):.3f}x')
print()
print('POWER of a 20-video sign test to reject "no rise" (H0: half the videos go up):')
for k in (20,18,16,14,12,11):
    p=2*sum(math.comb(20,i) for i in range(k,21))/2**20
    print(f'  if {k}/20 videos rise: sign-test p = {min(p,1):.4f}'
          + ('   <- significant' if p<0.05 else '   <- NOT significant'))
