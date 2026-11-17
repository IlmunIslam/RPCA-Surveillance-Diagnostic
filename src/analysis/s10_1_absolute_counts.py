"""RESEARCH_LOG.md §10.1 -- the absolute counts behind video_165's 199.8x.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 04:18 UTC. Added: this header and the working-directory lines.
Runs against the current results unchanged: its input has not changed since.

Run from the repo root:  python -m src.analysis.s10_1_absolute_counts
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv
r=list(csv.DictReader(open('results/metrics/ssrtd_real_results.csv')))[0]
n=180*320*300
s=int(r['S_claimed_px']); both=int(r['SE_both_px']); e=float(r['E_gt005_pct'])/100
print(f'voxels           {n:,}')
print(f'S-claimed        {s:,}  ({s/n*100:.4f}%)')
print(f'E-claimed        {int(e*n):,}  ({e*100:.4f}%)')
print(f'S and E both     {both:,}')
print(f'expected if independent  {s*e:.1f} voxels')
print(f'observed / expected      {both/(s*e):.1f}x')
