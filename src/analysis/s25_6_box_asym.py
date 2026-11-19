"""EXPLORATORY (not pre-registered): the E:S density asymmetry between background
and annotated-foreground voxels, using raw rates only -- no ratio-of-ratios, so no
denominator can do the work. Found while de-confounding s24.4's registered test.

RESEARCH_LOG.md §25.6 (EXPLORATORY). Provenance: session scratch script, first run 2026-11-07 17:30 UTC; moved
into the repo 2026-11-18 with only the project path made relative. See section 28.
Run from the repo root:  python -m src.analysis.s25_6_box_asym
"""
import csv
import math
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parents[2]  # was a hard-coded absolute path
# 2026-11-19: the printed threshold labels are corrected (RESEARCH_LOG.md section 31.7).
# The mask keys '001'/'005' are thresholds 0.01/0.05, but the original printed them as
# 0.{thr} = '0.001'/'0.005'. Labels now print 0.{thr[1:]}. No computed value changes,
# and this is the only change to the original code besides PROJ.
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


reg = list(csv.DictReader(open(PROJ / "video_registry.csv", newline="", encoding="utf-8")))
occ = {r["video_id"]: float(r["box_occupancy"]) for r in
       csv.DictReader(open(PROJ / "results" / "metrics" / "box_occupancy.csv",
                           newline="", encoding="utf-8"))}
rows = {}
for i, r in enumerate(reg):
    vid = r["short_id"]
    Bv = box_mask(r["original_filename"].replace(".mp4", ""))
    d = np.load(R / f"{vid}__clean__f1__lam0.4__s0" / "supports.npz")
    n = int(np.prod(d["shape"]))
    rec = {}
    for thr in ("001", "005"):
        S = np.unpackbits(d[f"S_gt{thr}"])[:n].astype(bool).reshape(H, W, T)
        E = np.unpackbits(d[f"E_gt{thr}"])[:n].astype(bool).reshape(H, W, T)
        for nm, m in (("in", Bv), ("out", ~Bv)):
            nn = int(m.sum())
            rec[f"S_{nm}_{thr}"] = int(S[m].sum()) / nn * 100
            rec[f"E_{nm}_{thr}"] = int(E[m].sum()) / nn * 100
    rows[vid] = rec
    if (i + 1) % 60 == 0:
        print(f"  ...{i+1}/180", flush=True)

for thr in ("005", "001"):
    print(f"\n=== threshold 0.{thr[1:]}: E:S density ratio, background vs annotated foreground ===")
    ri, ro, asym = [], [], []
    for vid, rec in rows.items():
        si, ei = rec[f"S_in_{thr}"], rec[f"E_in_{thr}"]
        so, eo = rec[f"S_out_{thr}"], rec[f"E_out_{thr}"]
        if si > 0 and so > 0:
            ri.append(ei / si)
            ro.append(eo / so)
            asym.append((eo / so) / (ei / si))
    n = len(asym)
    k = sum(1 for x in asym if x > 1)
    sp = min(1.0, 2 * sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n)
    print(f"  n={n}")
    print(f"  E:S ratio INSIDE boxes (annotated foreground): median {median(ri):.3f}")
    print(f"  E:S ratio OUTSIDE boxes (background):          median {median(ro):.3f}")
    print(f"  asymmetry (outside / inside): median {median(asym):.2f}x  "
          f"geo-mean {math.exp(mean([math.log(x) for x in asym])):.2f}x")
    print(f"  asymmetry > 1 on {k}/{n} videos, sign-test p={sp:.2e}")
    print(f"  videos where E outnumbers S in the background (E:S > 1): "
          f"{sum(1 for x in ro if x > 1)}/{n}")
    print(f"  videos where E outnumbers S inside boxes:                "
          f"{sum(1 for x in ri if x > 1)}/{n}")
    # does the asymmetry track scene emptiness? (the dose-response, de-confounded)
    vids = [v for v in rows if rows[v][f"S_in_{thr}"] > 0 and rows[v][f"S_out_{thr}"] > 0]
    a = [(rows[v][f"E_out_{thr}"] / rows[v][f"S_out_{thr}"]) /
         (rows[v][f"E_in_{thr}"] / rows[v][f"S_in_{thr}"]) for v in vids]
    fg = [float(x["fg"]) for x in csv.DictReader(
        open(PROJ / "results" / "metrics" / "box_occupancy.csv", newline="", encoding="utf-8"))
        if x["video_id"] in set(vids)]
    o = [occ[v] for v in vids]
    rs1, ps1 = spearman(fg, a)
    rs2, ps2 = spearman(o, a)
    print(f"  asymmetry vs foreground_density: rho {rs1:+.3f} (p~{ps1:.2e})")
    print(f"  asymmetry vs box_occupancy:      rho {rs2:+.3f} (p~{ps2:.2e})")
