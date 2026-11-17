"""Inputs to the s26 pre-registration. CLEAN-CONDITION SUPPORTS ONLY.
No impulse10 supports.npz or components.npz is opened. From the noise runs this reads
only (a) beta_X_final from the results CSV, already published in s21.2/s22, and
(b) noise_mask.npz, which is a property of the generator, not of the decomposition.

RESEARCH_LOG.md §26.1(2). Provenance: session scratch script, first run 2026-11-12 20:46 UTC; moved
into the repo 2026-11-18 with only the project path made relative. See section 28.
Run from the repo root:  python -m src.analysis.s26_1_lambda_volatility
"""
import csv
import math
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parents[2]  # was a hard-coded absolute path
sys.path.insert(0, str(PROJ))
from src.phase3_checkpoint import median, mean  # noqa: E402

A_DIR = PROJ / "data" / "annotations"
R = PROJ / "results" / "ssrtd_real" / "runs"
H, W, T, SCALE = 180, 320, 300, 4


def box_mask(stem):
    B = np.zeros((T, H, W), dtype=bool)
    for ln in open(A_DIR / (stem + ".viratdata.objects.txt")):
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


def unpack(d, key):
    n = int(np.prod(d["shape"]))
    return np.unpackbits(d[key])[:n].astype(bool).reshape(H, W, T)


def asym(S, E, B, U):
    i, o = B & U, ~B & U
    si, so = S[i].mean(), S[o].mean()
    ei, eo = E[i].mean(), E[o].mean()
    if min(si, so, ei, eo) == 0:
        return None
    return dict(A=(eo / so) / (ei / si), Ef=eo / ei, Sf=so / si)


reg = {r["short_id"]: r for r in csv.DictReader(
    open(PROJ / "video_registry.csv", newline="", encoding="utf-8"))}
rows = list(csv.DictReader(open(PROJ / "results/metrics/ssrtd_real_results.csv",
                                newline="", encoding="utf-8")))
bx = {}
for r in rows:
    if r["factor"] in ("1", "1.0") and float(r["lam"]) == 0.4:
        bx[(r["video_id"], r["condition"])] = float(r["beta_X_final"])

vids = sorted(p.name.split("__")[0] for p in R.glob("*__impulse10__f1__lam0.4__s0"))
gm = lambda xs: math.exp(mean([math.log(x) for x in xs]))
res = {k: [] for k in ("A", "Ef", "Sf")}
for v in vids:
    B = box_mask(reg[v]["original_filename"].replace(".mp4", ""))
    U = ~unpack(np.load(R / f"{v}__impulse10__f1__lam0.4__s0" / "noise_mask.npz"), "mask")
    a = {}
    for lam in ("0.4", "0.6"):
        d = np.load(R / f"{v}__clean__f1__lam{lam}__s0" / "supports.npz")
        a[lam] = asym(unpack(d, "S_gt001"), unpack(d, "E_gt001"), B, U)
    if a["0.4"] and a["0.6"]:
        for k in res:
            res[k].append(a["0.6"][k] / a["0.4"][k])
for k, xs in res.items():
    print(f"lam 0.4->0.6 paired ratio of {k:>2s}: geo-mean {gm(xs):.3f} range {min(xs):.3f}-{max(xs):.3f} "
          f"within [0.8,1.25] on {sum(0.8 <= x <= 1.25 for x in xs)}/{len(xs)}")
