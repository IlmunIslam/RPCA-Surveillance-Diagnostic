"""RESEARCH_LOG.md §10.3, run at the 10-VIDEO point (the arm was half done) -- is the enrichment-density correlation mechanical (support size).

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-10-19 08:27 UTC. Added: this header and the working-directory lines.
The results CSV is pinned to its first 10 data rows, its state when this ran:
the CSV is append-only in completion order with no timestamp column. Every row count
in the plausible window was tried; 10 is the largest whose output matches the
recorded output exactly (the full matching range is in RESEARCH_LOG.md section 30.3).
Only the `open(...)` of the CSV was changed, to `_csv_as_of(...)`.

Note: this ran on the first 10 clean-subset videos, not the 20 that §10 reports. Only one
number from it reached the record: §10.3's fg vs S_px rho +0.818, which is +0.976 at
n=20 (§30.3). §10.3's other numbers come from s10_3_odds_slope_pooled (n=20).

Run from the repo root:  python -m src.analysis.s10_3_mechanical_check
"""
import io, os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# ---- CSV pinned to the state it was in when this script first ran (see header) ----
CSV_ROWS_AT_ORIGINAL_RUN = 10


def _csv_as_of(path, n=CSV_ROWS_AT_ORIGINAL_RUN):
    """The append-only results CSV as it stood: header plus its first n data rows."""
    lines = open(path, newline="", encoding="utf-8").read().splitlines(keepends=True)
    return io.StringIO("".join(lines[:n + 1]))
# ---- original code below ----
import csv, math
from src.phase3_checkpoint import pearson, spearman
rows=list(csv.DictReader(_csv_as_of('results/metrics/ssrtd_real_results.csv')))
n=180*320*300
d=[]
for r in rows:
    S=int(r['S_claimed_px']); both=int(r['SE_both_px'])
    E=float(r['E_gt005_pct'])/100*n
    exp=S*E/n
    enr=both/exp
    # 2x2 odds ratio, invariant to neither marginal being huge
    s_only=S-both; e_only=E-both; neither=n-S-E+both
    orat=(both*neither)/(s_only*e_only) if s_only>0 and e_only>0 else float('nan')
    d.append((r['video_id'], float(r['foreground_density']), S, E, both, enr, orat))

print(f"{'video':11s} {'fg%':>6s} {'S_px':>7s} {'E_px':>8s} {'enrich':>7s} {'oddsR':>7s}")
for v,fg,S,E,both,enr,orat in sorted(d,key=lambda x:x[1]):
    print(f'{v:11s} {fg:6.3f} {S:7d} {E:8.0f} {enr:7.1f} {orat:7.1f}')

fg=[x[1] for x in d]; S=[x[2] for x in d]; enr=[x[5] for x in d]; orat=[x[6] for x in d]
lS=[math.log(x) for x in S]; lE=[math.log(x) for x in enr]
print()
print('log(enrichment) vs log(S_px)      slope-check  Pearson r %+.3f' % pearson(lS,lE)[0])
print('enrichment   vs S_claimed_px      Spearman rho %+.3f' % spearman(S,enr)[0])
print('enrichment   vs foreground_dens   Spearman rho %+.3f' % spearman(fg,enr)[0])
print('odds ratio   vs foreground_dens   Spearman rho %+.3f (p~%.3f)' % spearman(fg,orat))
print('odds ratio   vs S_claimed_px      Spearman rho %+.3f' % spearman(S,orat)[0])
print()
print('fg vs S_px   Spearman rho %+.3f  <- how tightly fg determines support size' % spearman(fg,S)[0])
