"""Section 24 analysis. Read-only. Implements 24.2's definition exactly.

RESEARCH_LOG.md §25.1-§25.4 (analyses specified in §24). Provenance: session scratch script, first run 2026-11-07 17:21 UTC; moved
into the repo 2026-11-18 with only the project path made relative. See section 28.
Run from the repo root:  python -m src.analysis.s25_box_analysis
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
from src.phase3_checkpoint import median, mean, sd, spearman, pearson  # noqa: E402

A = PROJ / "data" / "annotations"
R = PROJ / "results" / "ssrtd_real" / "runs"
H, W, T = 180, 320, 300
SCALE = 4


def box_mask(stem):
    """B[t, y, x] bool: covered by >=1 box. Plus per-frame object counts.
    24.2: all types, frames 0-299, floor/ceil, clipped, w<=0 or h<=0 dropped,
    frames with no rows contribute 0 (not skipped)."""
    B = np.zeros((T, H, W), dtype=bool)
    counts = np.zeros(T, dtype=np.int32)
    f = A / (stem + ".viratdata.objects.txt")
    with open(f) as fh:
        for ln in fh:
            p = ln.split()
            if len(p) < 8:
                continue
            fr = int(p[2])
            if not (0 <= fr < T):
                continue
            x, y, w, h = (int(p[3]), int(p[4]), int(p[5]), int(p[6]))
            if w <= 0 or h <= 0:
                continue
            x0 = max(0, x // SCALE)
            y0 = max(0, y // SCALE)
            x1 = min(W, -((-(x + w)) // SCALE))   # ceil
            y1 = min(H, -((-(y + h)) // SCALE))
            if x1 <= x0 or y1 <= y0:
                continue
            B[fr, y0:y1, x0:x1] = True
            counts[fr] += 1
    return B, counts


def supports(run, thr):
    d = np.load(R / run / "supports.npz")
    n = int(np.prod(d["shape"]))
    S = np.unpackbits(d[f"S_gt{thr}"])[:n].astype(bool)
    E = np.unpackbits(d[f"E_gt{thr}"])[:n].astype(bool)
    return S.reshape(H, W, T), E.reshape(H, W, T)


def enrich(S, E):
    s, e, n = int(S.sum()), int(E.sum()), S.size
    if s == 0 or e == 0:
        return None
    return (int(np.count_nonzero(S & E)) / s) / (e / n)


def main():
    reg = list(csv.DictReader(open(PROJ / "video_registry.csv", newline="", encoding="utf-8")))
    rows = list(csv.DictReader(open(PROJ / "results" / "metrics" / "ssrtd_real_results.csv",
                                    newline="", encoding="utf-8")))
    clean = {r["video_id"]: r for r in rows
             if r["condition"] == "clean" and float(r["factor"]) == 1.0
             and abs(float(r["lam"]) - 0.4) < 1e-9}
    out = []
    for i, r in enumerate(reg):
        vid, stem = r["short_id"], r["original_filename"].replace(".mp4", "")
        B, counts = box_mask(stem)
        occ = B.mean() * 100.0
        zero_frames = int((counts == 0).sum())
        rec = dict(video_id=vid, box_occupancy=occ, zero_frames=zero_frames,
                   mean_objs=float(counts.mean()),
                   fg=float(clean[vid]["foreground_density"]))
        Bv = np.transpose(B, (1, 2, 0))        # -> (H, W, T) to match supports
        run = f"{vid}__clean__f1__lam0.4__s0"
        for thr in ("001", "005"):
            S, E = supports(run, thr)
            rec[f"enr_{thr}"] = enrich(S, E)
            rec[f"in_{thr}"] = enrich(S[Bv], E[Bv])
            rec[f"out_{thr}"] = enrich(S[~Bv], E[~Bv])
        out.append(rec)
        if (i + 1) % 30 == 0:
            print(f"  ...{i+1}/180", flush=True)

    with open(PROJ / "results" / "metrics" / "box_occupancy.csv", "w",
              newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        wr.writeheader()
        wr.writerows(out)

    occ = [r["box_occupancy"] for r in out]
    fg = [r["fg"] for r in out]
    print("\n=== ANALYSIS 1: box_occupancy vs foreground_density, n=180 ===")
    rs, ps = spearman(fg, occ)
    rp, pp = pearson(fg, occ)
    print(f"  Spearman rho {rs:+.3f} (p~{ps:.2e})   Pearson r {rp:+.3f} (p~{pp:.2e})")
    print(f"  AGREEMENT THRESHOLD was rho >= +0.70  ->  "
          f"{'MET' if rs >= 0.70 else 'NOT MET'}")
    print(f"  box_occupancy %: min {min(occ):.4f} median {median(occ):.4f} max {max(occ):.4f}")
    print(f"  foreground_density %: min {min(fg):.4f} median {median(fg):.4f} max {max(fg):.4f}")
    zf = [r["zero_frames"] for r in out]
    print(f"  frames (of 300) with zero annotated objects: median {median(zf):.0f}, "
          f"videos with >=1 such frame: {sum(1 for z in zf if z > 0)}/180, "
          f"videos entirely empty: {sum(1 for z in zf if z == 300)}")

    print("\n=== ANALYSIS 1b: the dose-response recomputed against box_occupancy ===")
    for thr in ("005", "001"):
        e = [r[f"enr_{thr}"] for r in out]
        ok = [(a, b, c) for a, b, c in zip(occ, fg, e) if c]
        o2, f2, e2 = [x[0] for x in ok], [x[1] for x in ok], [x[2] for x in ok]
        r_occ, p_occ = spearman(o2, e2)
        r_fg, p_fg = spearman(f2, e2)
        print(f"  thr 0.{thr[1:]} (n={len(e2)}): enrichment vs box_occupancy "
              f"rho {r_occ:+.3f} (p~{p_occ:.2e})   |   vs foreground_density "
              f"rho {r_fg:+.3f} (p~{p_fg:.2e})   | diff {abs(r_occ - r_fg):.3f}")

    print("\n=== ANALYSIS 1c: the empty end -- 20 lowest foreground_density videos ===")
    srt = sorted(out, key=lambda r: r["fg"])[:20]
    rank_occ = {r["video_id"]: i for i, r in enumerate(sorted(out, key=lambda r: r["box_occupancy"]))}
    inboth = sum(1 for r in srt if rank_occ[r["video_id"]] < 20)
    print(f"  of the 20 lowest-fg videos, {inboth}/20 are also in the 20 "
          f"lowest-box_occupancy")
    print(f"  {'video':11s} {'fg%':>8s} {'occ%':>8s} {'occ rank':>9s} {'enr005':>8s}")
    for r in srt[:10]:
        e = r["enr_005"]
        print(f"  {r['video_id']:11s} {r['fg']:8.4f} {r['box_occupancy']:8.4f} "
              f"{rank_occ[r['video_id']]:9d} {(f'{e:.1f}x' if e else '--'):>8s}")

    print("\n=== ANALYSIS 2: enrichment INSIDE vs OUTSIDE the boxes (s24.4) ===")
    for thr in ("005", "001"):
        pairs = [(r[f"in_{thr}"], r[f"out_{thr}"]) for r in out
                 if r[f"in_{thr}"] and r[f"out_{thr}"]]
        ratio = [o / i for i, o in pairs]
        lr = [math.log(x) for x in ratio]
        outgt = sum(1 for x in ratio if x > 1)
        n = len(ratio)
        sp = min(1.0, 2 * sum(math.comb(n, k) for k in range(outgt, n + 1)) / 2 ** n)
        print(f"  thr 0.{thr[1:]}: n={n}  inside median {median([i for i, o in pairs]):8.2f}x  "
              f"outside median {median([o for i, o in pairs]):8.2f}x")
        print(f"            OUTSIDE/INSIDE ratio: median {median(ratio):.3f}x  "
              f"geo-mean {math.exp(mean(lr)):.3f}x  range {min(ratio):.2f}-{max(ratio):.2f}x")
        print(f"            outside > inside on {outgt}/{n} videos, sign-test p={sp:.2e}")
    print("\nwrote results/metrics/box_occupancy.csv")


if __name__ == "__main__":
    main()
