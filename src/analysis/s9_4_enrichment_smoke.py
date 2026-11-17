"""RESEARCH_LOG.md §9.4 -- the enrichment ratio on the smoke run, clean vs impulse10, by voxel population.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 03:51 UTC. Added: this header and the working-directory lines.
Runs against the current results unchanged: its input has not changed since.

Run from the repo root:  python -m src.analysis.s9_4_enrichment_smoke
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import numpy as np, pathlib
base = pathlib.Path('results/scratch/phase3_smoke/runs')

def load(run):
    d = base/run
    z = np.load(d/'supports.npz')
    shape = tuple(int(x) for x in z['shape']); n = int(np.prod(shape))
    S = np.unpackbits(z['S_gt005'])[:n].astype(bool)
    E = np.unpackbits(z['E_gt005'])[:n].astype(bool)
    m = None
    if (d/'noise_mask.npz').exists():
        nz = np.load(d/'noise_mask.npz')
        raw = np.asarray(nz['mask']).ravel()
        m = (np.unpackbits(raw)[:n].astype(bool) if raw.size*8 >= n and raw.dtype==np.uint8 and raw.size < n
             else raw.astype(bool))
    return S, E, m, n

def enr(S, E, n, label):
    both = int((S & E).sum()); s = int(S.sum()); e = int(E.sum())
    print(f'{label:36s} S {s/n*100:6.3f}%  E {e/n*100:6.3f}%  P(E|S) {both/s*100:6.3f}%  enrichment {(both/s)/(e/n):5.3f}x')

S, E, _, n = load('video_01__clean__f1__lam0.4__s0')
enr(S, E, n, 'clean, all voxels')
Sn, En, m, n = load('video_01__impulse10__f1__lam0.4__s0')
enr(Sn, En, n, 'impulse10, all voxels')
print(f'  corrupted fraction {m.mean()*100:.3f}%  (expected 10%)')
k = ~m
enr(Sn[k], En[k], int(k.sum()), 'impulse10, UNcorrupted voxels only')
enr(Sn[m], En[m], int(m.sum()), 'impulse10, corrupted voxels only')
