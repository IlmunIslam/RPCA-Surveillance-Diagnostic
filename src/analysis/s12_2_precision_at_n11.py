"""RESEARCH_LOG.md §12.2 (RETRACTED claim, n=11) -- E's denoising precision/recall vs foreground density at n=11.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 17:17 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 31 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 31 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s12_2_precision_at_n11
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 31


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv
from src.phase3_checkpoint import spearman, median
rows=[r for r in csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')) if r['condition']=='impulse10']
rows.sort(key=lambda r: float(r['foreground_density']))
print(f"{'video':11s} {'fg%':>6s} {'rec005':>7s} {'prec005':>8s} {'dB gain':>8s} {'E!=0%':>6s} {'SE_ovl%':>8s}")
fg,pr,rc,gain=[],[],[],[]
for r in rows:
    g=float(r['psnr_LS_vs_clean'])-float(r['psnr_noisy_vs_clean'])
    print(f"{r['video_id']:11s} {float(r['foreground_density']):6.3f} {float(r['E_recall_005']):7.3f} "
          f"{float(r['E_precision_005']):8.3f} {g:8.2f} {float(r['E_nonzero_pct']):6.1f} {float(r['SE_overlap_005']):8.2f}")
    fg.append(float(r['foreground_density'])); pr.append(float(r['E_precision_005']))
    rc.append(float(r['E_recall_005'])); gain.append(g)
print()
print('n = %d' % len(rows))
print('precision@.05 vs fg_density  Spearman rho %+.3f (p~%.4f)' % spearman(fg,pr))
print('recall@.05    vs fg_density  Spearman rho %+.3f (p~%.4f)' % spearman(fg,rc))
print('dB gain       vs fg_density  Spearman rho %+.3f (p~%.4f)' % spearman(fg,gain))
print('median precision %.3f  median recall %.3f  median gain %.2f dB' % (median(pr), median(rc), median(gain)))
