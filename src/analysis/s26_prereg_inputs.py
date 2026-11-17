"""Inputs to the s26 pre-registration. CLEAN-CONDITION SUPPORTS ONLY.
No impulse10 supports.npz or components.npz is opened. From the noise runs this reads
only (a) beta_X_final from the results CSV, already published in s21.2/s22, and
(b) noise_mask.npz, which is a property of the generator, not of the decomposition.

RESEARCH_LOG.md §26.1(3), §26.4. Provenance: session scratch script, first run 2026-11-12 UTC; moved
into the repo 2026-11-18 with only the project path made relative. See section 28.
Run from the repo root:  python -m src.analysis.s26_prereg_inputs
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
assert len(vids) == 20, vids
M = 0.01
out = []
for v in vids:
    B = box_mask(reg[v]["original_filename"].replace(".mp4", ""))
    nm = np.load(R / f"{v}__impulse10__f1__lam0.4__s0" / "noise_mask.npz")
    C = unpack(nm, "mask")
    U = ~C
    # spillover-excluded population: uncorrupted with no corrupted 6-neighbour
    nb = C.copy()
    nb[1:] |= C[:-1]; nb[:-1] |= C[1:]
    nb[:, 1:] |= C[:, :-1]; nb[:, :-1] |= C[:, 1:]
    nb[:, :, 1:] |= C[:, :, :-1]; nb[:, :, :-1] |= C[:, :, 1:]
    d = np.load(R / f"{v}__clean__f1__lam0.4__s0" / "supports.npz")
    S01, S05, E01, E05 = (unpack(d, k) for k in ("S_gt001", "S_gt005", "E_gt001", "E_gt005"))
    a11, a15 = asym(S01, E01, B, U), asym(S01, E05, B, U)
    a55, a51 = asym(S05, E05, B, U), asym(S05, E01, B, U)
    d6 = np.load(R / f"{v}__clean__f1__lam0.6__s0" / "supports.npz")
    a11_l6 = asym(unpack(d6, "S_gt001"), unpack(d6, "E_gt001"), B, U)
    bc, bn = bx[(v, "clean")], bx[(v, "impulse10")]
    tau, k = 1.0 / bc, bc / bn
    m_exact = M + (k - 1) * tau
    rec = dict(v=v, corr_in=C[B].mean(), corr_out=C[~B].mean(), spill_keep=(~nb).mean(),
               tau=tau, k=k, m_exact=m_exact, a11=a11, a15=a15, a55=a55, a51=a51,
               a11_l6=a11_l6)
    if a11 and a15:
        e = math.log(a15["A"] / a11["A"]) / math.log(5)
        eE = math.log(a15["Ef"] / a11["Ef"]) / math.log(5)
        rec.update(e=e, eE=eE,
                   c_exact=(m_exact / M) ** e, c_cons=k ** e,
                   cE_exact=(m_exact / M) ** eE, cE_cons=k ** eE)
    # interpolation check where clean float components exist
    cp = R / f"{v}__clean__f1__lam0.4__s0" / "components.npz"
    if cp.exists() and a11:
        cz = np.load(cp)
        Ec, Sc = np.abs(cz["E"]), np.abs(cz["S"])
        Sm = Sc > M
        assert (Sm == S01).all(), "components/supports disagree at S>0.01"
        for nm_, mm in (("exact", m_exact), ("cons", min(k * M, 0.05))):
            ax = asym(Sm, Ec > mm, B, U)
            rec[f"val_{nm_}"] = ax["A"] / a11["A"] if ax else None
    out.append(rec)
    print(f"  {v} done", flush=True)

print("\n=== gates (no outcome data) ===")
print(f"corruption rate inside boxes  median {median([r['corr_in'] for r in out]):.4f} "
      f"range {min(r['corr_in'] for r in out):.4f}-{max(r['corr_in'] for r in out):.4f}")
print(f"corruption rate outside boxes median {median([r['corr_out'] for r in out]):.4f} "
      f"range {min(r['corr_out'] for r in out):.4f}-{max(r['corr_out'] for r in out):.4f}")
print(f"spillover-excluded population keeps {median([r['spill_keep'] for r in out])*100:.1f}% of voxels")
print(f"tau_clean = 1/beta_X_clean: max {max(r['tau'] for r in out):.5f} "
      f"(must be <= m=0.01 for k*m to be a conservative over-shift)")
print(f"k = beta_X clean/noise: median {median([r['k'] for r in out]):.3f} "
      f"range {min(r['k'] for r in out):.3f}-{max(r['k'] for r in out):.3f}")
print(f"exact emulated E threshold m': median {median([r['m_exact'] for r in out]):.5f} "
      f"max {max(r['m_exact'] for r in out):.5f}")

print("\n=== clean asymmetry on the uncorrupted voxel set (the clean side of the pair) ===")
ok = [r for r in out if r["a11"]]
print(f"thr 0.01 defined {len(ok)}/20; A median {median([r['a11']['A'] for r in ok]):.2f}x, "
      f">1 on {sum(r['a11']['A'] > 1 for r in ok)}/{len(ok)}")
ok5 = [r for r in out if r["a55"]]
print(f"thr 0.05 defined {len(ok5)}/20; A median {median([r['a55']['A'] for r in ok5]):.2f}x")

print("\n=== confound 2: E-threshold elasticity of the asymmetry (S fixed at 0.01) ===")
el = [r for r in out if "e" in r]
print(f"elasticity e (dlnA/dln m_E): median {median([r['e'] for r in el]):+.3f} "
      f"range {min(r['e'] for r in el):+.3f}..{max(r['e'] for r in el):+.3f}  "
      f"(negative = raising E's threshold SHRINKS the asymmetry)")
print(f"  E-factor elasticity:        median {median([r['eE'] for r in el]):+.3f}")
gm = lambda xs: math.exp(mean([math.log(x) for x in xs]))
for nm_ in ("c_exact", "c_cons"):
    xs = [r[nm_] for r in el]
    print(f"predicted confound-only paired ratio ({nm_}): geo-mean {gm(xs):.3f} "
          f"median {median(xs):.3f} range {min(xs):.3f}-{max(xs):.3f}")
for nm_ in ("cE_exact", "cE_cons"):
    xs = [r[nm_] for r in el]
    print(f"   E-factor only ({nm_}): geo-mean {gm(xs):.3f} range {min(xs):.3f}-{max(xs):.3f}")
print("interpolation check against float components (clean, 3 videos):")
for r in out:
    if "val_exact" in r:
        print(f"  {r['v']}: exact-threshold ratio {r['val_exact']:.3f} vs log-linear "
              f"{r.get('c_exact', float('nan')):.3f} | k*m ratio {r['val_cons']:.3f} "
              f"vs {r.get('c_cons', float('nan')):.3f}")

print("\n=== reference scale: an unrelated perturbation (clean lam 0.4 -> 0.6, thr 0.01) ===")
lr = [r["a11_l6"]["A"] / r["a11"]["A"] for r in out if r["a11"] and r["a11_l6"]]
print(f"paired A ratio: geo-mean {gm(lr):.3f} median {median(lr):.3f} "
      f"range {min(lr):.3f}-{max(lr):.3f} n={len(lr)}")
