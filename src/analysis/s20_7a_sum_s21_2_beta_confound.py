"""RESEARCH_LOG.md §20.7a and §21.2 -- the per-video S+E sum check and the beta_X confound.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-06 23:47 UTC. Only this header and the working-directory lines
were added. See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s20_7a_sum_s21_2_beta_confound
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, collections
from src.phase3_checkpoint import median, mean, sd, spearman
rows=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv',newline='',encoding='utf-8')))
def fl(r,k):
    v=(r.get(k) or '').strip()
    try: return float(v)
    except: return None
cl={r['video_id']:r for r in rows if r['arm']=='clean-subset'}
no={r['video_id']:r for r in rows if r['arm']=='noise-subset'}
ids=sorted(cl)
print('--- CONFOUND CHECK: does the E threshold (factor/beta_X) differ clean vs noise at lam 0.4? ---')
for k in ('beta_X_final','beta_f_final','beta_X_grew_n','n_iter','err_X_final'):
    c=[fl(cl[i],k) for i in ids]; n=[fl(no[i],k) for i in ids]
    rat=[b/a for a,b in zip(c,n) if a]
    print(f"{k:18s} clean med {median(c):12.4f}   noise med {median(n):12.4f}   "
          f"per-video ratio med {median(rat):.3f} ({min(rat):.3f}-{max(rat):.3f})")
print()
print('--- per-video S and E rates, clean vs noise, lam 0.4 (ALL voxels) ---')
for k in ('S_gt005_pct','E_gt005_pct'):
    c=[fl(cl[i],k) for i in ids]; n=[fl(no[i],k) for i in ids]
    print(f"{k:14s} clean med {median(c):8.4f}  noise med {median(n):8.4f}  "
          f"ratio med {median([b/a for a,b in zip(c,n) if a]):.3f}")
print()
print('--- my s20.2 "sum nearly conserved" claim, re-checked PER VIDEO ---')
g=collections.defaultdict(dict)
for r in rows:
    if r['arm'] in ('clean-subset','lambda-sweep'): g[float(r['lam'])][r['video_id']]=r
tot=lambda l,i: fl(g[l][i],'S_gt005_pct')+fl(g[l][i],'E_gt005_pct')
ch=[tot(1.0,i)/tot(0.2,i) for i in ids]
print(f'per-video (S_rate+E_rate) change lam 0.2 -> 1.0: median {median(ch):.3f}x '
      f'range {min(ch):.2f}-{max(ch):.2f}x; videos within +/-10% of conserved: '
      f'{sum(1 for x in ch if 0.9<=x<=1.1)}/{len(ch)}')
