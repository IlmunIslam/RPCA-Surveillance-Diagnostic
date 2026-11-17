"""RESEARCH_LOG.md §12.1 -- uncorrupted-voxel enrichment for the 20 noise runs.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 23:44 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 40 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 40 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Run from the repo root:  python -m src.analysis.s12_1_uncorrupted_enrichment
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 40


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import numpy as np, csv, pathlib
from src.phase3_checkpoint import spearman, median
runs=pathlib.Path('results/ssrtd_real/runs')
clean={r['video_id']: r for r in csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')) if r['condition']=='clean'}
rows=[r for r in csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')) if r['condition']=='impulse10']
rows.sort(key=lambda r: float(r['foreground_density']))
print(f"{'video':11s} {'fg%':>6s} {'clean_enr':>10s} {'noise_all':>10s} {'noise_unc':>10s} {'corrupt':>8s}")
fg,ce,nu=[],[],[]
for r in rows:
    v=r['video_id']; d=runs/f'{v}__impulse10__f1__lam0.4__s0'
    z=np.load(d/'supports.npz'); shape=tuple(int(x) for x in z['shape']); n=int(np.prod(shape))
    S=np.unpackbits(z['S_gt005'])[:n].astype(bool); E=np.unpackbits(z['E_gt005'])[:n].astype(bool)
    m=np.unpackbits(np.load(d/'noise_mask.npz')['mask'].ravel())[:n].astype(bool)
    k=~m; Sk,Ek=S[k],E[k]; nk=int(k.sum())
    enr_unc=((Sk&Ek).sum()/Sk.sum())/(Ek.sum()/nk)
    enr_all=float(r['SE_overlap_005'])/float(r['E_gt005_pct'])
    c=clean[v]; enr_cl=float(c['SE_overlap_005'])/float(c['E_gt005_pct'])
    print(f'{v:11s} {float(r["foreground_density"]):6.3f} {enr_cl:9.1f}x {enr_all:9.2f}x {enr_unc:9.2f}x {m.mean()*100:7.3f}%')
    fg.append(float(r['foreground_density'])); ce.append(enr_cl); nu.append(enr_unc)
print()
print('uncorrupted-voxel enrichment: median %.2fx range %.2f-%.2f' % (median(nu), min(nu), max(nu)))
print('clean-arm enrichment:         median %.1fx range %.1f-%.1f' % (median(ce), min(ce), max(ce)))
print('noise_unc vs fg_density  rho %+.3f (p~%.4f)' % spearman(fg,nu))
print('noise_unc vs clean_enr   rho %+.3f (p~%.4f)' % spearman(ce,nu))
