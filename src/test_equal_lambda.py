"""
One-off test: SS-RTD with EQUAL penalties (lam_s == lam_n == 0.001) on video_01.

Background: the documented SS-RTD behavior is winner-takes-all — lam_s > lam_n
forces foreground into N. This test probes the degenerate equal-lambda case to
see which component captures the foreground, and whether the result is
deterministic across two identical runs (the ADMM here is seeded from zeros, so
it *should* be — this confirms it empirically rather than assuming).

Run from the project directory as a module:
    python -m src.test_equal_lambda
"""

from pathlib import Path

import numpy as np

from src.preprocessing import load_video_frames, frames_to_tensor, load_registry
from src.ssrtd import ssrtd

PROJECT_DIR = Path(__file__).parent.parent
VIDEO_DIR = PROJECT_DIR / "data" / "videos"
REGISTRY = PROJECT_DIR / "video_registry.csv"

LAM_S = 0.001
LAM_N = 0.001
MAX_ITER = 500
TOL = 1e-7
NNZ_EPS = 1e-6


def classify_winner(s_nnz, n_nnz, split_ratio=0.1):
    """
    Decide which component captured the foreground.

    - If one component's nonzero % is < split_ratio of the other, the larger
      one 'won' (winner-takes-all).
    - Otherwise the energy is SPLIT across both.
    """
    if s_nnz < split_ratio * n_nnz:
        return "N wins (S collapsed)"
    if n_nnz < split_ratio * s_nnz:
        return "S wins (N collapsed)"
    return "SPLIT (both components active)"


def run_once(X, label):
    print(f"\n{'='*60}")
    print(f"{label}: ssrtd(lam_s={LAM_S}, lam_n={LAM_N})")
    print(f"{'='*60}")

    L, S, N, n_iter = ssrtd(X, lam_s=LAM_S, lam_n=LAM_N,
                            max_iter=MAX_ITER, tol=TOL)

    s_nnz = float(np.mean(np.abs(S) > NNZ_EPS) * 100)
    n_nnz = float(np.mean(np.abs(N) > NNZ_EPS) * 100)
    recon_err = float(np.linalg.norm(X - L - S - N))
    converged = n_iter < MAX_ITER
    winner = classify_winner(s_nnz, n_nnz)

    return {
        "label": label,
        "s_nnz": s_nnz,
        "n_nnz": n_nnz,
        "winner": winner,
        "recon_err": recon_err,
        "n_iter": n_iter,
        "converged": converged,
    }


def print_result(r):
    print(f"\n--- {r['label']} summary ---")
    print(f"  S nonzero            : {r['s_nnz']:.4f}%")
    print(f"  N nonzero            : {r['n_nnz']:.4f}%")
    print(f"  Winner               : {r['winner']}")
    print(f"  Reconstruction error : {r['recon_err']:.6e}  (||X - L - S - N||)")
    if r["converged"]:
        print(f"  Convergence          : converged in {r['n_iter']} iterations")
    else:
        print(f"  Convergence          : HIT MAX_ITER ({MAX_ITER}) WITHOUT CONVERGING")


def main():
    # Resolve video_01 -> filename via the registry (same source the pipeline uses)
    registry = load_registry(REGISTRY)
    row = registry[registry["short_id"] == "video_01"].iloc[0]
    video_path = VIDEO_DIR / row["original_filename"]
    print(f"Loading video_01 -> {row['original_filename']}")

    frames = load_video_frames(video_path, max_frames=300)
    X = frames_to_tensor(frames)
    print(f"Tensor shape: {X.shape}")

    r1 = run_once(X, "RUN 1")
    print_result(r1)

    r2 = run_once(X, "RUN 2")
    print_result(r2)

    # ---- Side-by-side comparison ----
    print(f"\n{'='*60}")
    print("SIDE-BY-SIDE")
    print(f"{'='*60}")
    print(f"{'metric':<24}{'RUN 1':>18}{'RUN 2':>18}")
    print(f"{'-'*60}")
    print(f"{'S nonzero %':<24}{r1['s_nnz']:>18.4f}{r2['s_nnz']:>18.4f}")
    print(f"{'N nonzero %':<24}{r1['n_nnz']:>18.4f}{r2['n_nnz']:>18.4f}")
    print(f"{'winner':<24}{r1['winner']:>18}{r2['winner']:>18}")
    print(f"{'recon error':<24}{r1['recon_err']:>18.6e}{r2['recon_err']:>18.6e}")
    print(f"{'n_iter':<24}{r1['n_iter']:>18}{r2['n_iter']:>18}")
    print(f"{'converged':<24}{str(r1['converged']):>18}{str(r2['converged']):>18}")

    # ---- Determinism verdict ----
    same_winner = r1["winner"] == r2["winner"]
    s_close = abs(r1["s_nnz"] - r2["s_nnz"]) < 1e-6
    n_close = abs(r1["n_nnz"] - r2["n_nnz"]) < 1e-6
    print(f"\n{'='*60}")
    if same_winner and s_close and n_close:
        print("VERDICT: DETERMINISTIC — both runs identical, same winner, "
              "sparsity matches to <1e-6.")
    elif same_winner:
        print("VERDICT: same winner both runs, but sparsity %% differ "
              f"(S diff {abs(r1['s_nnz']-r2['s_nnz']):.2e}, "
              f"N diff {abs(r1['n_nnz']-r2['n_nnz']):.2e}).")
    else:
        print("VERDICT: ARBITRARY — winner FLIPPED between runs "
              f"(RUN1: {r1['winner']} / RUN2: {r2['winner']}).")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
