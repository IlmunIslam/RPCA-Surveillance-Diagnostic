"""Is the inside/outside enrichment gap an artifact of E being denser inside boxes?
Enrichment = P(E|S)/P(E), so a high P(E) inside compresses it toward 1 mechanically
(the same denominator effect as RESEARCH_LOG s20.7b). Report the raw conditional
P(E|S) alongside, which has no such denominator, plus both component rates.

RESEARCH_LOG.md §25.4. Provenance: session scratch script, first run 2026-11-07 17:26 UTC; moved
into the repo 2026-11-18 with only the project path made relative. See section 28.
Run from the repo root:  python -m src.analysis.s25_4_box_confound
"""
import csv
import math
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parents[2]  # was a hard-coded absolute path
sys.path.insert(0, str(PROJ))
from src.phase3_checkpoint import median, mean, spearman  # noqa: E402

A = PROJ / "data" / "annotations"
R = PROJ / "results" / "ssrtd_real" / "runs"
H, W, T, SCALE = 180, 320, 300, 4


def box_mask(stem):
    B = np.zeros((T, H, W), dtype=bool)
    for ln in open(A / (stem + ".viratdata.objects.txt")):
        p = ln.split()
        if len(p) < 8:
            continue
        fr = int(p[2])
        if not (0 <= fr < T):
            continue
        x, y, w, h = int(p[3]), int(p[4]), int(p[5]), int(p[6])
        if w <= 0 or h <= 0:
            continue
        x0, y0 = max(0, x // SCALE), max(0, y // SCALE)
        x1, y1 = min(W, -((-(x + w)) // SCALE)), min(H, -((-(y + h)) // SCALE))
        if x1 > x0 and y1 > y0:
            B[fr, y0:y1, x0:x1] = True
    return np.transpose(B, (1, 2, 0))


def stats(S, E):
    s, e, n = int(S.sum()), int(E.sum()), S.size
    if s == 0 or e == 0:
        return None
    both = int(np.count_nonzero(S & E))
    return dict(s=s / n * 100, e=e / n * 100, pes=both / s * 100,
                enr=(both / s) / (e / n), n=n)


reg = list(csv.DictReader(open(PROJ / "video_registry.csv", newline="", encoding="utf-8")))
res = {"001": [], "005": []}
for i, r in enumerate(reg):
    vid = r["short_id"]
    Bv = box_mask(r["original_filename"].replace(".mp4", ""))
    d = np.load(R / f"{vid}__clean__f1__lam0.4__s0" / "supports.npz")
    n = int(np.prod(d["shape"]))
    for thr in ("001", "005"):
        S = np.unpackbits(d[f"S_gt{thr}"])[:n].astype(bool).reshape(H, W, T)
        E = np.unpackbits(d[f"E_gt{thr}"])[:n].astype(bool).reshape(H, W, T)
        a, b = stats(S[Bv], E[Bv]), stats(S[~Bv], E[~Bv])
        if a and b:
            res[thr].append((vid, a, b))
    if (i + 1) % 60 == 0:
        print(f"  ...{i+1}/180", flush=True)

for thr in ("005", "001"):
    v = res[thr]
    print(f"\n=== threshold 0.{thr}, n={len(v)} ===")
    print(f"{'population':>12s} {'S>thr%':>9s} {'E>thr%':>9s} {'raw P(E|S)%':>12s} "
          f"{'enrichment':>11s} {'voxels':>12s}")
    for name, k in (("INSIDE", 1), ("OUTSIDE", 2)):
        print(f"{name:>12s} {median([x[k]['s'] for x in v]):9.4f} "
              f"{median([x[k]['e'] for x in v]):9.4f} "
              f"{median([x[k]['pes'] for x in v]):12.3f} "
              f"{median([x[k]['enr'] for x in v]):10.2f}x "
              f"{median([x[k]['n'] for x in v]):12,.0f}")
    # the decisive comparison: does the RAW conditional also favour outside?
    rr = [x[2]['pes'] / x[1]['pes'] for x in v if x[1]['pes'] > 0]
    er = [x[2]['enr'] / x[1]['enr'] for x in v]
    n = len(rr)
    sp = min(1.0, 2 * sum(math.comb(n, k) for k in range(sum(1 for z in rr if z > 1), n + 1)) / 2 ** n)
    print(f"  OUTSIDE/INSIDE on the RAW conditional P(E|S): median {median(rr):.3f}x "
          f"({sum(1 for z in rr if z > 1)}/{n} favour outside, p={sp:.2e})")
    print(f"  OUTSIDE/INSIDE on ENRICHMENT:                 median {median(er):.3f}x")
    print(f"  E-rate inside/outside (the denominator effect): median "
          f"{median([x[1]['e'] / x[2]['e'] for x in v]):.2f}x denser inside")
    # how much of the enrichment gap does the denominator alone explain?
    expl = [(x[1]['e'] / x[2]['e']) for x in v]
    print(f"  if the gap were PURELY the denominator, enrichment ratio would be "
          f"{median(expl):.2f}x; observed {median(er):.2f}x")
