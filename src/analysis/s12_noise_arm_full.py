"""RESEARCH_LOG.md §12.1-§12.2 -- the full noise-subset arm (n=20).

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 23:44 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 60 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 60 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s12_noise_arm_full
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 60


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv
from src.phase3_checkpoint import spearman, median, mean, sd
rows=[r for r in csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')) if r['condition']=='impulse10']
rows.sort(key=lambda r: float(r['foreground_density']))
n=180*320*300
print(f"{'video':11s} {'fg%':>6s} {'rec005':>7s} {'prec005':>8s} {'dBgain':>7s} {'SSIM':>6s} {'E!=0%':>6s} {'enrich':>7s}")
fg,pr,rc,gain,enr,ssim=[],[],[],[],[],[]
for r in rows:
    g=float(r['psnr_LS_vs_clean'])-float(r['psnr_noisy_vs_clean'])
    e=float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
    print(f"{r['video_id']:11s} {float(r['foreground_density']):6.3f} {float(r['E_recall_005']):7.3f} "
          f"{float(r['E_precision_005']):8.3f} {g:7.2f} {float(r['ssim_LS_vs_clean']):6.3f} "
          f"{float(r['E_nonzero_pct']):6.1f} {e:7.2f}")
    fg.append(float(r['foreground_density'])); pr.append(float(r['E_precision_005']))
    rc.append(float(r['E_recall_005'])); gain.append(g); enr.append(e)
    ssim.append(float(r['ssim_LS_vs_clean']))
print()
print('n=%d  recall005: min %.4f max %.4f (sd %.5f)' % (len(rc), min(rc), max(rc), sd(rc)))
print('precision005: median %.3f range %.3f-%.3f' % (median(pr), min(pr), max(pr)))
print('dB gain: median %.2f range %.2f-%.2f | SSIM median %.3f' % (median(gain), min(gain), max(gain), median(ssim)))
print('enrichment under noise: median %.2fx range %.2f-%.2f' % (median(enr), min(enr), max(enr)))
print()
for name,v in (('precision005',pr),('recall005',rc),('dB gain',gain),('enrichment',enr)):
    r,p=spearman(fg,v); print('%-14s vs fg_density  rho %+.3f (p~%.4f)' % (name,r,p))
