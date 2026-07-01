"""
Parameter sweep — proves the SS-RTD S/N component collapse is controlled by the
lambda ratio (lam_s vs lam_n), not by scene content (foreground density).

Selects 20 videos evenly spaced across the foreground-density range and runs
SS-RTD only (no Tensor RPCA, no compression) at 5 lambda configurations each.
100 video-config rows total -> results/metrics/param_sweep.csv.

Resumable: skips any (video_id, lam_s, lam_n) already present in param_sweep.csv.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.preprocessing import load_video_frames, frames_to_tensor
from src.ssrtd import ssrtd
from src.metrics import compute_sparsity

PROJECT_DIR = Path(__file__).parent.parent
VIDEO_DIR = Path(r"S:\works\Video compression Research\RPCA_Hybrid_Project\data\videos")
REGISTRY = PROJECT_DIR / "video_registry.csv"
ALL_RESULTS_CSV = PROJECT_DIR / "results" / "metrics" / "all_results.csv"
SWEEP_CSV = PROJECT_DIR / "results" / "metrics" / "param_sweep.csv"

N_VIDEOS = 20
N_RESERVE_TOP = 4   # reserve the N highest-density videos to cover busy scenes
N_SPACED = N_VIDEOS - N_RESERVE_TOP   # evenly space the remaining 16 across the rest

# The 5 lambda configurations. Ratio is what matters:
#   lam_n > lam_s  -> S wins (foreground stays in S)
#   lam_s > lam_n  -> N wins (foreground pushed into N — the collapse)
#   equal          -> tie-break control
CONFIGS = [
    {"name": "config_1", "lam_s": 0.001, "lam_n": 0.002},   # lam_n > lam_s
    {"name": "config_2", "lam_s": 0.002, "lam_n": 0.001},   # lam_s > lam_n
    {"name": "config_3", "lam_s": 0.001, "lam_n": 0.001},   # equal
    {"name": "config_4", "lam_s": 0.01,  "lam_n": 0.001},   # lam_s >> lam_n (production default)
    {"name": "config_5", "lam_s": 0.001, "lam_n": 0.01},    # lam_n >> lam_s
]


def select_videos():
    """Pick 20 videos covering the foreground_density range, over-weighting busy
    scenes so at least N_RESERVE_TOP (4) videos have density > 1.0.

    Strategy: reserve the N_RESERVE_TOP highest-density videos, then evenly space
    the remaining N_SPACED (16) across the rest by sorted rank
    (np.linspace(0, len(rest)-1, N_SPACED), which includes the lowest-density
    video). The 20 are returned density-ascending. Because the top 4 densities
    are all > 1.0, this guarantees >= 4 busy scenes; the spaced 16 may add more.

    Returns list of (video_id, foreground_density) tuples, density-ascending.
    """
    df = pd.read_csv(ALL_RESULTS_CSV)
    df = df.sort_values("foreground_density").reset_index(drop=True)

    top = df.iloc[len(df) - N_RESERVE_TOP:]          # N highest-density videos
    rest = df.iloc[:len(df) - N_RESERVE_TOP]          # everything below them

    idx = np.linspace(0, len(rest) - 1, N_SPACED).round().astype(int)
    idx = sorted(set(idx))                            # guard against dup indices
    spaced = rest.iloc[idx]

    chosen = (pd.concat([spaced, top])
                .drop_duplicates(subset="video_id")
                .sort_values("foreground_density"))

    selection = list(zip(chosen["video_id"].astype(str), chosen["foreground_density"]))

    n_busy = sum(1 for _, d in selection if d > 1.0)
    print(f"Selected {len(selection)} of {len(df)} videos "
          f"({N_RESERVE_TOP} reserved top-density + {N_SPACED} evenly spaced):")
    print(f"  {'video_id':<12} {'foreground_density':>18}")
    for vid, dens in selection:
        flag = "  <- busy (>1.0)" if dens > 1.0 else ""
        print(f"  {vid:<12} {dens:>18.4f}{flag}")
    print(f"  density range: {selection[0][1]:.4f} (lowest) "
          f"-> {selection[-1][1]:.4f} (highest)")
    print(f"  videos with density > 1.0: {n_busy}")

    return selection


def resolve_video_path(video_id, registry_df):
    row = registry_df[registry_df["short_id"] == video_id]
    if row.empty:
        raise ValueError(f"{video_id} not found in registry")
    return VIDEO_DIR / row.iloc[0]["original_filename"]


def load_done_pairs():
    """Return set of (video_id, lam_s, lam_n) already recorded, for resume."""
    if not SWEEP_CSV.exists():
        return set()
    df = pd.read_csv(SWEEP_CSV)
    return {
        (str(r.video_id), round(float(r.lam_s), 6), round(float(r.lam_n), 6))
        for r in df.itertuples(index=False)
    }


def append_row(row):
    SWEEP_CSV.parent.mkdir(parents=True, exist_ok=True)
    row_df = pd.DataFrame([row])
    if SWEEP_CSV.exists():
        row_df.to_csv(SWEEP_CSV, mode="a", header=False, index=False)
    else:
        row_df.to_csv(SWEEP_CSV, index=False)


def run_sweep():
    selection = select_videos()
    registry_df = pd.read_csv(REGISTRY)
    done = load_done_pairs()

    total_pairs = len(selection) * len(CONFIGS)
    print(f"\nTotal video-config pairs: {total_pairs} | "
          f"already done: {len(done)} | remaining: {total_pairs - len(done)}\n")

    completed = 0
    sweep_start = time.time()

    for vid, fg_density in selection:
        # Which configs still need running for this video?
        pending = [c for c in CONFIGS
                   if (vid, round(c["lam_s"], 6), round(c["lam_n"], 6)) not in done]
        if not pending:
            print(f"[{vid}] all {len(CONFIGS)} configs already done — skipping load")
            continue

        # Load + build the tensor ONCE per video; all 5 configs share the same X.
        video_path = resolve_video_path(vid, registry_df)
        print(f"[{vid}] loading {video_path.name} (fg_density={fg_density:.4f}) "
              f"— {len(pending)} config(s) to run")
        frames = load_video_frames(video_path, max_frames=300)
        X = frames_to_tensor(frames)  # (H, W, T)

        for cfg in pending:
            lam_s, lam_n = cfg["lam_s"], cfg["lam_n"]
            print(f"  -> {cfg['name']}: lam_s={lam_s}, lam_n={lam_n}")
            t0 = time.time()
            L, S, N, n_iter = ssrtd(X, lam_s=lam_s, lam_n=lam_n)
            elapsed = round((time.time() - t0) / 60, 2)

            s_nonzero = round(100.0 - compute_sparsity(S), 4)
            n_nonzero = round(100.0 - compute_sparsity(N), 4)
            winner = "S" if s_nonzero > n_nonzero else "N"
            recon_error = float(np.linalg.norm(X - L - S - N))

            append_row({
                "video_id": vid,
                "foreground_density": fg_density,
                "config": cfg["name"],
                "lam_s": lam_s,
                "lam_n": lam_n,
                "s_nonzero_pct": s_nonzero,
                "n_nonzero_pct": n_nonzero,
                "winner": winner,
                "recon_error": recon_error,
                "n_iter": n_iter,
                "runtime_min": elapsed,
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            completed += 1
            print(f"     winner={winner}  s_nonzero={s_nonzero:.3f}%  "
                  f"n_nonzero={n_nonzero:.3f}%  recon_err={recon_error:.4e}  "
                  f"({elapsed} min)  [{completed} run this session]")

    total_hours = round((time.time() - sweep_start) / 3600, 2)
    print(f"\nSweep session done: {completed} pairs run, {total_hours} h.")
    print_summary()


def print_summary():
    """Pivot: for each config, how many videos had S win vs N win."""
    if not SWEEP_CSV.exists():
        print("No param_sweep.csv yet.")
        return
    df = pd.read_csv(SWEEP_CSV)
    print("\n=== Summary: winner counts per config (out of "
          f"{df['video_id'].nunique()} videos) ===")
    pivot = (df.groupby(["config", "lam_s", "lam_n", "winner"])
               .size().unstack("winner", fill_value=0))
    for col in ("S", "N"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot[["S", "N"]]
    print(pivot.to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SS-RTD lambda-ratio parameter sweep")
    parser.add_argument("--select-only", action="store_true",
                        help="Print the 20-video selection and exit (no SS-RTD runs)")
    parser.add_argument("--summary-only", action="store_true",
                        help="Print the winner-count summary from existing CSV and exit")
    args = parser.parse_args()

    if args.select_only:
        select_videos()
    elif args.summary_only:
        print_summary()
    else:
        run_sweep()
