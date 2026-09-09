from pathlib import Path

import numpy as np

from src.preprocessing import load_video_frames, frames_to_tensor
from src.ssrtd import ssrtd

PROJECT_DIR = Path(__file__).parent.parent
REGISTRY = PROJECT_DIR / "video_registry.csv"
VIDEO_DIR = PROJECT_DIR / "data" / "videos"
VIDEO_ID = "video_39"
FILENAME = "VIRAT_S_010002_05_000397_000420.mp4"

PARAM_GRID = [
    {"lam_s": 0.001, "lam_n": 0.002},   # (a) current baseline
    {"lam_s": 0.01,  "lam_n": 0.001},   # (b) flip ratio
    {"lam_s": 0.05,  "lam_n": 0.001},   # (c) stronger flip
    {"lam_s": 0.1,   "lam_n": 0.001},   # (d) aggressive
]


def main():
    video_path = VIDEO_DIR / FILENAME
    print(f"Loading {VIDEO_ID} frames...")
    frames = load_video_frames(video_path, max_frames=300)
    X = frames_to_tensor(frames)
    print(f"Tensor shape: {X.shape}\n")
    print("=" * 60)

    results = []

    for i, params in enumerate(PARAM_GRID, start=1):
        lam_s = params["lam_s"]
        lam_n = params["lam_n"]
        label = ["(a) baseline", "(b) flip ratio", "(c) stronger flip", "(d) aggressive"][i - 1]

        print(f"\nRun {i}/4 {label}")
        print(f"  lam_s={lam_s}, lam_n={lam_n}")

        L, S, N, n_iter = ssrtd(X, lam_s=lam_s, lam_n=lam_n, max_iter=500, tol=1e-7)

        s_nnz = round(np.mean(np.abs(S) > 1e-6) * 100, 4)
        n_nnz = round(np.mean(np.abs(N) > 1e-6) * 100, 4)
        recon_err = round(float(np.linalg.norm(X - L - S - N)), 6)

        print(f"  S nonzero : {s_nnz:.4f}%")
        print(f"  N nonzero : {n_nnz:.4f}%")
        print(f"  Recon err : {recon_err:.6f}")
        print(f"  n_iter    : {n_iter}")

        results.append({
            "label": label,
            "lam_s": lam_s,
            "lam_n": lam_n,
            "s_nnz": s_nnz,
            "n_nnz": n_nnz,
            "recon_err": recon_err,
            "n_iter": n_iter,
        })

    # Summary table
    print("\n")
    print("=" * 60)
    print("SUMMARY — SS-RTD parameter search on video_39")
    print("=" * 60)
    hdr = f"{'Label':<20} {'lam_s':>6} {'lam_n':>6} {'S_nnz%':>8} {'N_nnz%':>8} {'ReconErr':>10} {'iters':>6}"
    sep = "-" * len(hdr)
    print(hdr)
    print(sep)
    for r in results:
        print(
            f"{r['label']:<20} {r['lam_s']:>6.3f} {r['lam_n']:>6.3f} "
            f"{r['s_nnz']:>8.4f} {r['n_nnz']:>8.4f} "
            f"{r['recon_err']:>10.6f} {r['n_iter']:>6}"
        )
    print(sep)


if __name__ == "__main__":
    main()
