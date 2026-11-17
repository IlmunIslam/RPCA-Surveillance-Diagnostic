"""RESEARCH_LOG.md s26 -- the PRE-REGISTERED analysis, committed before it was run.

Question: does E's foreground/background distribution survive when E is given
legitimate work (impulse noise), once the noise-induced rise in E's threshold is
accounted for?

Statistic (per video, threshold 0.01, uncorrupted voxels U of that video's noise run,
the SAME voxel set in both arms):

    Ef(arm) = P(|E| > 0.01 | outside boxes, U) / P(|E| > 0.01 | inside boxes, U)
    r_v     = Ef(impulse10) / Ef(clean)                       (lambda 0.4, factor 1)

Threshold adjustment (s26.4), computed from CLEAN supports only:

    e_v  = ln( Ef_clean(E>0.05) / Ef_clean(E>0.01) ) / ln 5    elasticity in E's threshold
    k_v  = beta_X_final(clean) / beta_X_final(impulse10)      E threshold is factor/beta_X
    m'_v = 0.01 + (k_v - 1) / beta_X_final(clean)             exact emulated threshold
    c_v  = (m'_v / 0.01) ** e_v                               confound-only ratio
    r*_v = r_v / c_v                                          primary
    cons: c_v = k_v ** e_v                                    worst-case confound credit

Verdicts are fixed in s26.5 and implemented in verdict() below, unchanged after commit.

Usage:
    python -m src.prereg_s26_e_selectivity --plumbing-test   # clean vs clean; opens no noise support
    python -m src.prereg_s26_e_selectivity                   # the registered run
"""
import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

PROJ = Path(__file__).resolve().parents[1]
A_DIR = PROJ / "data" / "annotations"
R = PROJ / "results" / "ssrtd_real" / "runs"
H, W, T, SCALE = 180, 320, 300, 4
M = 0.01
BAND = (0.80, 1.25)


def box_mask(stem, inner=False):
    """s24.2 mapping (outer: floor start, ceil end). inner=True is the s26.6
    secondary: ceil start, floor end, so no true-background pixel is counted inside."""
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
        if inner:
            x0, y0 = -((-x) // SCALE), -((-y) // SCALE)
            x1, y1 = (x + w) // SCALE, (y + h) // SCALE
        else:
            x0, y0 = x // SCALE, y // SCALE
            x1, y1 = -((-(x + w)) // SCALE), -((-(y + h)) // SCALE)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if x1 > x0 and y1 > y0:
            B[fr, y0:y1, x0:x1] = True
    return np.transpose(B, (1, 2, 0))


def unpack(d, key):
    n = int(np.prod(d["shape"]))
    return np.unpackbits(d[key])[:n].astype(bool).reshape(H, W, T)


def ef(E, B, U):
    i, o = E[B & U].mean(), E[~B & U].mean()
    return None if i == 0 or o == 0 else o / i


def geo_ci(xs):
    lx = np.log(np.asarray(xs))
    n, mu = len(lx), lx.mean()
    h = stats.t.ppf(0.975, n - 1) * lx.std(ddof=1) / math.sqrt(n)
    return math.exp(mu), math.exp(mu - h), math.exp(mu + h)


def verdict(prim, cons, sec_spill, sec_inner):
    g, lo, hi = prim
    if lo >= BAND[0] and hi <= BAND[1]:
        bad = [nm for nm, s in (("spillover-excluded", sec_spill), ("inner boxes", sec_inner))
               if not (BAND[0] <= s[0] <= BAND[1])]
        return ("INCONCLUSIVE (primary PRESERVED, secondary outside band: "
                + ", ".join(bad) + ")") if bad else "PRESERVED -- H1 supported"
    if hi < 1.0 and cons[0] < BAND[0]:
        return "WITHDRAWN -- H0 supported, H1 falsified"
    if lo > BAND[1]:
        return "GROWN -- H1 falsified (direction predicted by neither hypothesis)"
    return "INCONCLUSIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plumbing-test", action="store_true",
                    help="use the CLEAN supports for both arms; no noise support is opened")
    a = ap.parse_args()

    reg = {r["short_id"]: r for r in csv.DictReader(
        open(PROJ / "video_registry.csv", newline="", encoding="utf-8"))}
    bx = {}
    for r in csv.DictReader(open(PROJ / "results/metrics/ssrtd_real_results.csv",
                                 newline="", encoding="utf-8")):
        if float(r["factor"]) == 1.0 and float(r["lam"]) == 0.4:
            bx[(r["video_id"], r["condition"])] = float(r["beta_X_final"])
    vids = sorted(p.name.split("__")[0] for p in R.glob("*__impulse10__f1__lam0.4__s0"))
    assert len(vids) == 20, vids

    rows = []
    for v in vids:
        stem = reg[v]["original_filename"].replace(".mp4", "")
        B, Bi = box_mask(stem), box_mask(stem, inner=True)
        C = unpack(np.load(R / f"{v}__impulse10__f1__lam0.4__s0" / "noise_mask.npz"), "mask")
        U = ~C
        nb = C.copy()
        nb[1:] |= C[:-1]; nb[:-1] |= C[1:]
        nb[:, 1:] |= C[:, :-1]; nb[:, :-1] |= C[:, 1:]
        nb[:, :, 1:] |= C[:, :, :-1]; nb[:, :, :-1] |= C[:, :, 1:]
        U6 = ~nb
        dc = np.load(R / f"{v}__clean__f1__lam0.4__s0" / "supports.npz")
        noise_dir = "clean" if a.plumbing_test else "impulse10"
        dn = np.load(R / f"{v}__{noise_dir}__f1__lam0.4__s0" / "supports.npz")
        Ec01, Ec05, En01 = unpack(dc, "E_gt001"), unpack(dc, "E_gt005"), unpack(dn, "E_gt001")
        efc, efc5, efn = ef(Ec01, B, U), ef(Ec05, B, U), ef(En01, B, U)
        if None in (efc, efc5, efn):
            print(f"  {v}: undefined (an E rate is zero) -- excluded per s26.5")
            continue
        bc, bn = bx[(v, "clean")], bx[(v, "impulse10")]
        k = bc / bn
        e = math.log(efc5 / efc) / math.log(5)
        c = ((M + (k - 1) / bc) / M) ** e
        c_cons = k ** e
        r = efn / efc
        rs = ef(En01, B, U6) / ef(Ec01, B, U6)
        ri = ef(En01, Bi, U) / ef(Ec01, Bi, U)
        rows.append(dict(v=v, r=r, c=c, c_cons=c_cons, rstar=r / c, rcons=r / c_cons,
                         rspill=rs / c, rinner=ri / c, efc=efc, efn=efn))
        print(f"  {v}: Ef clean {efc:.4f} noise {efn:.4f}  r {r:.3f}  c {c:.3f}  "
              f"r* {r / c:.3f}  r*cons {r / c_cons:.3f}", flush=True)

    n = len(rows)
    prim = geo_ci([x["rstar"] for x in rows])
    raw = geo_ci([x["r"] for x in rows])
    cons = geo_ci([x["rcons"] for x in rows])
    spill = geo_ci([x["rspill"] for x in rows])
    inner = geo_ci([x["rinner"] for x in rows])
    inband = sum(BAND[0] <= x["rstar"] <= BAND[1] for x in rows)
    print(f"\nn = {n}{'   [PLUMBING TEST: clean vs clean]' if a.plumbing_test else ''}")
    for nm, s in (("r* (PRIMARY, exact adjustment)", prim), ("r unadjusted", raw),
                  ("r* conservative adjustment", cons), ("r* spillover-excluded", spill),
                  ("r* inner boxes", inner)):
        print(f"  {nm:32s} geo-mean {s[0]:.3f}  95% CI {s[1]:.3f}-{s[2]:.3f}")
    print(f"  per-video r* inside [{BAND[0]}, {BAND[1]}]: {inband}/{n}")
    print(f"\nVERDICT: {verdict(prim, cons, spill, inner)}")


if __name__ == "__main__":
    sys.exit(main())
