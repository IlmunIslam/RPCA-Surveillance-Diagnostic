"""
First full-ADMM measurement on ONE real VIRAT video (Phase 3 preflight).

Answers two questions the plan has only projected so far:
  * peak memory of the full ssrtd_real loop (projection: 4.3-5.4 GB; the only
    measured numbers are per-component and Candela-scaled)
  * wall clock per video (projection: ~31 min, extrapolated from Candela)
and gives the first real look at whether SS-RTD's smooth-foreground assumption
survives sharp surveillance foreground -- the actual research question.

Peak memory is psutil's memory_info().peak_wset (Windows peak working set,
tracked by the OS), NOT a polled rss, which can miss the spike between samples.

Writes ONLY to results/scratch/ -- never to ssrtd_real_results.csv. A stray row
there would interact with the Phase 3 resume-skip logic. Data (history CSV,
components NPZ, summary JSON) is written BEFORE the figure, so a plotting
failure cannot lose the run.

Launch DETACHED (PHASE3_NOTES.md section 1); at ~30-40 min this sits at the
harness kill boundary:
  Start-Process -FilePath cmd.exe -ArgumentList '/c python -u -m src.measure_virat_one >> logs/measure_virat_one.log 2>&1' -WorkingDirectory "<repo>" -WindowStyle Hidden
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from src.preprocessing import frames_to_tensor, load_registry, load_video_frames
from src.ssrtd_real import E_THRESHOLD_FACTOR, feasible_ranks, ssrtd_real, tucker_ranks

PROJECT_DIR = Path(__file__).parent.parent
OUT_DIR = PROJECT_DIR / "results" / "scratch" / "measure_virat_one"

# dataviz reference palette (light), as in gate_candela.py
SURFACE, INK_PRIMARY, INK_SECONDARY, INK_MUTED, BASELINE = (
    "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#c3c2b7")
DIVERGING = ("#2a78d6", "#f0efec", "#e34948")


def mb(x):
    return x / 2**20


def plot_frame(X, r, t, out_path, video_id):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    div = LinearSegmentedColormap.from_list("diverging", DIVERGING)

    def sym(a):
        v = float(np.percentile(np.abs(a), 99)) or 1.0
        return -v, v

    panels = [
        ("Input frame", X[:, :, t], "gray", (0, 1)),
        ("L — static background", r["L"][:, :, t], "gray", (0, 1)),
        ("S — smooth foreground (TV)", r["S"][:, :, t], div, sym(r["S"][:, :, t])),
        ("E — sparse noise (L1)", r["E"][:, :, t], div, sym(r["E"][:, :, t])),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.6), facecolor=SURFACE)
    for ax, (title, img, cmap, (vmin, vmax)) in zip(axes.flat, panels):
        im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title, color=INK_PRIMARY, fontsize=10, loc="left")
        ax.axis("off")
        if cmap is div:
            cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
            cb.ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY, labelsize=8)
            cb.outline.set_edgecolor(BASELINE)
    fig.suptitle(f"Real SS-RTD on VIRAT {video_id}, frame {t + 1} of {X.shape[2]}  ·  "
                 f"λ = {r['lam']:g}, factor {r['factor']:g}, {r['n_iter']} iterations",
                 color=INK_PRIMARY, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=SURFACE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", default=None, help="registry short_id; default: first row")
    ap.add_argument("--lam", type=float, default=0.4)
    ap.add_argument("--factor", type=float, default=1.0,
                    help="E-threshold factor; 1.0 is the gate's choice "
                         f"(code default is {E_THRESHOLD_FACTOR})")
    ap.add_argument("--max-iter", type=int, default=100)
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()

    out = Path(args.out)
    if "ssrtd_real_results" in str(out) or out.name.startswith("metrics"):
        sys.exit("refusing to write into a Phase 3 results path; this is a scratch run")
    out.mkdir(parents=True, exist_ok=True)

    proc = psutil.Process()
    t_start = datetime.now()
    print("=" * 72)
    print(f"measure_virat_one  started {t_start:%Y-%m-%d %H:%M:%S}")
    print(f"  baseline working set {mb(proc.memory_info().wset):.0f} MB, "
          f"peak so far {mb(proc.memory_info().peak_wset):.0f} MB")

    df = load_registry(PROJECT_DIR / "video_registry.csv")
    row = df[df.short_id == args.video_id].iloc[0] if args.video_id else df.iloc[0]
    path = PROJECT_DIR / "data" / "videos" / row["original_filename"]

    t0 = time.perf_counter()
    X = frames_to_tensor(load_video_frames(path, max_frames=300))
    t_load = time.perf_counter() - t0
    ranks = tucker_ranks(X.shape)
    print(f"  video   {row['short_id']}  ({row['original_filename']})")
    print(f"  tensor  {X.shape}  range [{X.min():.3f}, {X.max():.3f}]  mean {X.mean():.4f}"
          f"  load {t_load:.1f} s")
    print(f"  ranks   {ranks} -> attainable {feasible_ranks(X.shape, ranks)}")
    print(f"  lam {args.lam}  factor {args.factor}  max_iter {args.max_iter}  tol {args.tol:g}")
    print(f"  after load: working set {mb(proc.memory_info().wset):.0f} MB")
    print("-" * 72, flush=True)

    t0 = time.perf_counter()
    r = ssrtd_real(X, lam=args.lam, max_iter=args.max_iter, tol=args.tol,
                   factor=args.factor, verbose=True)
    wall = time.perf_counter() - t0
    mi = proc.memory_info()
    peak_mb, cur_mb = mb(mi.peak_wset), mb(mi.wset)

    # ---- data first ---------------------------------------------------------
    hist = pd.DataFrame(r["history"])
    for k, v in (("method", "ssrtd_real"), ("video_id", row["short_id"]),
                 ("factor", args.factor), ("lam", args.lam)):
        hist.insert(0, k, v)
    hist.to_csv(out / "history.csv", index=False)
    np.savez_compressed(out / "components.npz",
                        L=r["L"].astype(np.float32), S=r["S"].astype(np.float32),
                        E=r["E"].astype(np.float32))

    resid = float(np.linalg.norm((X - r["L"] - r["S"] - r["E"]).ravel()) / np.linalg.norm(X.ravel()))
    l1 = lambda a: float(np.abs(a).sum())
    summary = {
        "purpose": "Phase 3 preflight: first measured full-ADMM peak memory and wall clock on one VIRAT video",
        "started": t_start.isoformat(timespec="seconds"),
        "video_id": row["short_id"], "file": row["original_filename"],
        "shape": list(X.shape), "lam": args.lam, "factor": args.factor,
        "max_iter": args.max_iter, "tol": args.tol,
        "ranks_requested": list(ranks), "ranks_attainable": list(feasible_ranks(X.shape, ranks)),
        "n_iter": r["n_iter"], "converged": r["converged"],
        "wall_seconds": wall, "seconds_per_iteration": wall / max(r["n_iter"], 1),
        "peak_working_set_mb": peak_mb, "final_working_set_mb": cur_mb,
        "projection_peak_mb": [4.3 * 1024, 5.4 * 1024], "projection_minutes": 31,
        "final_relChg_E": r["history"][-1]["relChg_E"],
        "final_err_X": r["history"][-1]["err_X"],
        "beta_X_final": r["beta_X"], "beta_f_final": r["beta_f"],
        "beta_X_grew_iters": int(hist["beta_X_grew"].sum()),
        "constraint_residual_rel": resid,
        "E_nonzero_fraction": float(np.mean(r["E"] != 0)),
        "l1_mass": {"L": l1(r["L"]), "S": l1(r["S"]), "E": l1(r["E"])},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    print("-" * 72)
    print(f"  n_iter {r['n_iter']}  converged {r['converged']}  wall {wall/60:.1f} min "
          f"({wall/max(r['n_iter'],1):.2f} s/iter)")
    print(f"  PEAK working set {peak_mb:.0f} MB  (projection 4,403-5,530 MB)  "
          f"final {cur_mb:.0f} MB")
    print(f"  final relChg_E {summary['final_relChg_E']:.3e}  err_X {summary['final_err_X']:.4g}  "
          f"beta_X {r['beta_X']:.4g} (grew {summary['beta_X_grew_iters']}/{r['n_iter']})")
    print(f"  constraint residual {100*resid:.3f}% of ||X||  E nonzero {100*summary['E_nonzero_fraction']:.1f}%  "
          f"l1 mass L/S/E {l1(r['L']):.3g}/{l1(r['S']):.3g}/{l1(r['E']):.3g}")
    print(f"  data written to {out}", flush=True)

    # ---- figure last --------------------------------------------------------
    try:
        plot_frame(X, r, X.shape[2] // 2, out / "decomposition_frame.png", row["short_id"])
        print("  figure written: decomposition_frame.png")
    except Exception as exc:
        print(f"  WARNING: figure failed ({type(exc).__name__}: {exc}); data is safe")
    print(f"finished {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
