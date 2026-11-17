"""RESEARCH_LOG.md §10.2 -- batch video_01 against the smoke run (identical statistics).

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 12:20 UTC. Added: this header and the working-directory lines.
Runs against the current results unchanged: its input has not changed since.

Run from the repo root:  python -m src.analysis.s10_2_batch_vs_smoke_video01
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv
batch=[r for r in csv.DictReader(open('results/metrics/ssrtd_real_results.csv')) if r['video_id']=='video_01'][0]
smoke=[r for r in csv.DictReader(open('results/scratch/phase3_smoke/smoke_results.csv')) if r['condition']=='clean'][0]
keys=['S_gt005_pct','E_gt005_pct','SE_overlap_005','S_claimed_px','SE_both_px','l1_L','l1_S','l1_E',
      'err_X_final','relChg_L_final','psnr_LS_vs_X','ssim_LS_vs_X','L_crf28_kb','E_crf28_kb']
diff=[k for k in keys if batch[k]!=smoke[k]]
print('identical on', len(keys)-len(diff), 'of', len(keys), 'statistics')
for k in diff: print('  DIFFERS', k, smoke[k], '->', batch[k])
print('commit  smoke', smoke['commit'][:7], '-> batch', batch['commit'][:7])
