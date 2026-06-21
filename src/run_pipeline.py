import argparse
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.preprocessing import load_video_frames, frames_to_tensor, frames_to_matrix
from src.tensor_rpca import tensor_rpca
from src.ssrtd import ssrtd
from src.hybrid_encoder import build_hybrid, hybrid_to_frames
from src.metrics import compute_psnr_sequence, compute_ssim_sequence, compute_sparsity, compute_foreground_density
from src.compression import run_compression_analysis

PROJECT_DIR = Path(__file__).parent.parent
VIDEO_DIR = Path("VIDEO_DIR_PLACEHOLDER")
RESULTS_DIR = PROJECT_DIR / "results"
METRICS_CSV = RESULTS_DIR / "metrics" / "all_results.csv"

# Videos for which full component arrays + a sample-frame figure are persisted
# (paper figures only): video_01 + highest/lowest foreground_density from the
# first batch (video_108=3.13%, video_101=0.02%). All others save the CSV row only.
FIGURE_VIDEO_IDS = {"video_01", "video_101", "video_108"}


def save_figure_components(video_id, original_frames,
                           L_tensor, S_tensor,
                           L_ssrtd, S_ssrtd, N_ssrtd):
    """Persist the 5 component arrays (.npy) and a middle-frame visualization
    (.png) for the few videos used in paper figures. Components are (H, W, T);
    original_frames is (T, H, W)."""
    out_dir = RESULTS_DIR / "figures" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    np.save(out_dir / "L_tensor.npy", L_tensor)
    np.save(out_dir / "S_tensor.npy", S_tensor)
    np.save(out_dir / "L_ssrtd.npy",  L_ssrtd)
    np.save(out_dir / "S_ssrtd.npy",  S_ssrtd)
    np.save(out_dir / "N_ssrtd.npy",  N_ssrtd)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = original_frames.shape[0] // 2  # middle frame
    panels = [
        ("Original", original_frames[t]),
        ("L_tensor", L_tensor[:, :, t]),
        ("S_tensor", S_tensor[:, :, t]),
        ("L_ssrtd",  L_ssrtd[:, :, t]),
        ("S_ssrtd",  S_ssrtd[:, :, t]),
        ("N_ssrtd",  N_ssrtd[:, :, t]),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 5))
    for ax, (title, img) in zip(axes.ravel(), panels):
        ax.imshow(img, cmap="gray")
        ax.set_title(f"{title} (frame {t})", fontsize=9)
        ax.axis("off")
    fig.suptitle(f"{video_id} — component decomposition")
    fig.tight_layout()
    fig.savefig(out_dir / f"{video_id}_components_frame{t}.png", dpi=150)
    plt.close(fig)
    print(f"  [figures] Saved 5 .npy arrays + sample frame to {out_dir}")


def process_video(video_id, video_path, verbose=True):
    # ------------------------------------------------------------------
    # 1. LOAD
    # ------------------------------------------------------------------
    original_frames = load_video_frames(video_path, max_frames=300)
    T = original_frames.shape[0]
    X_tensor = frames_to_tensor(original_frames)   # (H, W, T)
    fg_density = compute_foreground_density(original_frames)
    print(f"\n=== Processing {video_id} === loaded {T} frames, fg_density={fg_density:.4f}%")

    # ------------------------------------------------------------------
    # 2. TENSOR RPCA
    # ------------------------------------------------------------------
    t0 = time.time()
    L_tensor, S_tensor, n_iter_rpca = tensor_rpca(X_tensor)
    tensor_time = round(time.time() - t0, 1)

    recon_tensor = np.transpose(L_tensor + S_tensor, (2, 0, 1))   # (T, H, W)
    mean_psnr_t, std_psnr_t, _ = compute_psnr_sequence(original_frames, recon_tensor)
    mean_ssim_t, std_ssim_t, _ = compute_ssim_sequence(original_frames, recon_tensor)
    s_sparsity_t = compute_sparsity(S_tensor)

    # Components are intermediate only — used for metrics/compression below,
    # not persisted (each save was ~0.27 GB and filled the disk). See change log.

    print(f"  Tensor RPCA: PSNR={mean_psnr_t:.2f} dB, SSIM={mean_ssim_t:.4f}, "
          f"S_sparsity={s_sparsity_t:.2f}%, time={tensor_time}s")

    # ------------------------------------------------------------------
    # 3. SS-RTD
    # ------------------------------------------------------------------
    t0 = time.time()
    L_ssrtd, S_ssrtd, N_ssrtd, n_iter_ssrtd = ssrtd(X_tensor, lam_s=0.01, lam_n=0.001)
    ssrtd_time = round(time.time() - t0, 1)

    recon_ssrtd = np.transpose(L_ssrtd + S_ssrtd + N_ssrtd, (2, 0, 1))  # (T, H, W) — full X=L+S+N (verification)
    mean_psnr_s, std_psnr_s, _ = compute_psnr_sequence(original_frames, recon_ssrtd)
    mean_ssim_s, std_ssim_s, _ = compute_ssim_sequence(original_frames, recon_ssrtd)
    s_sparsity_s = compute_sparsity(S_ssrtd)
    n_sparsity_s = compute_sparsity(N_ssrtd)

    # SS-RTD components kept in memory only (not persisted — see Tensor RPCA note).

    print(f"  SS-RTD: PSNR={mean_psnr_s:.2f} dB, SSIM={mean_ssim_s:.4f}, "
          f"S_sparsity={s_sparsity_s:.2f}%, N_sparsity={n_sparsity_s:.2f}%, time={ssrtd_time}s")

    # ------------------------------------------------------------------
    # 3b. PERSIST COMPONENTS FOR PAPER FIGURES (3 representative videos only)
    # ------------------------------------------------------------------
    if video_id in FIGURE_VIDEO_IDS:
        save_figure_components(
            video_id, original_frames,
            L_tensor, S_tensor,
            L_ssrtd, S_ssrtd, N_ssrtd,
        )

    # ------------------------------------------------------------------
    # 4. HYBRID
    # ------------------------------------------------------------------
    t0 = time.time()
    hybrid = build_hybrid(L_tensor, N_ssrtd)
    hybrid_frames = hybrid_to_frames(hybrid)
    hybrid_time = round(time.time() - t0, 1)

    mean_psnr_h, std_psnr_h, _ = compute_psnr_sequence(original_frames, hybrid_frames)
    mean_ssim_h, std_ssim_h, _ = compute_ssim_sequence(original_frames, hybrid_frames)

    # Nothing persisted here: hybrid_frames stays in memory and feeds the
    # compression step below (the hybrid file-size number is still measured —
    # a useful negative result), but no hybrid_reconstructed.mp4 is written.

    print(f"  Hybrid: PSNR={mean_psnr_h:.2f} dB, SSIM={mean_ssim_h:.4f}, time={hybrid_time}s")

    # ------------------------------------------------------------------
    # 5. COMPRESSION ANALYSIS
    # ------------------------------------------------------------------
    compression_dir = RESULTS_DIR / "compression" / video_id
    compression_dir.mkdir(parents=True, exist_ok=True)

    compression_results = run_compression_analysis(
        video_id, original_frames,
        L_tensor, S_tensor,
        L_ssrtd, S_ssrtd, N_ssrtd,
        hybrid_frames, compression_dir,
    )

    # Index compression results by label for easy lookup
    comp = {r["label"]: r for r in compression_results}

    # The H.264 mp4s were written only to measure their sizes; sizes are now
    # captured in `comp`, so delete the temp folder — each video should leave
    # behind only its CSV row.
    shutil.rmtree(compression_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 6. SAVE METRICS ROW  (was step 5 before compression was added)
    # ------------------------------------------------------------------
    results = {
        "video_id": video_id,
        "total_frames": T,
        "foreground_density": fg_density,
        "tensor_psnr": mean_psnr_t,
        "tensor_ssim": mean_ssim_t,
        "tensor_s_sparsity": s_sparsity_t,
        "tensor_time_s": tensor_time,
        "ssrtd_psnr": mean_psnr_s,
        "ssrtd_ssim": mean_ssim_s,
        "ssrtd_s_sparsity": s_sparsity_s,
        "ssrtd_n_sparsity": n_sparsity_s,
        "ssrtd_winner": "S" if s_sparsity_s < n_sparsity_s else "N",
        "ssrtd_s_nonzero_pct": round(100 - s_sparsity_s, 4),
        "ssrtd_n_nonzero_pct": round(100 - n_sparsity_s, 4),
        "ssrtd_time_s": ssrtd_time,
        "hybrid_psnr": mean_psnr_h,
        "hybrid_ssim": mean_ssim_h,
        "hybrid_time_s": hybrid_time,
        "original_ref_kb": comp.get("original", {}).get("reference_kb"),
        "original_comp_kb": comp.get("original", {}).get("compressed_kb"),
        "L_tensor_kb": comp.get("L_tensor", {}).get("compressed_kb"),
        "S_tensor_kb": comp.get("S_tensor", {}).get("compressed_kb"),
        "N_ssrtd_kb": comp.get("N_ssrtd", {}).get("compressed_kb"),
        "hybrid_kb": comp.get("hybrid", {}).get("compressed_kb"),
        "hybrid_compression_ratio": comp.get("hybrid", {}).get("compression_ratio"),
        "hybrid_psnr_after_h264": comp.get("hybrid", {}).get("psnr_after_h264"),
        "hybrid_ssim_after_h264": comp.get("hybrid", {}).get("ssim_after_h264"),
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    METRICS_CSV.parent.mkdir(parents=True, exist_ok=True)
    row_df = pd.DataFrame([results])
    if METRICS_CSV.exists():
        existing = pd.read_csv(METRICS_CSV)
        combined = pd.concat([existing, row_df], ignore_index=True)
        combined.to_csv(METRICS_CSV, index=False)
    else:
        row_df.to_csv(METRICS_CSV, index=False)
    print("  Results saved to all_results.csv")

    # ------------------------------------------------------------------
    # 6. SUMMARY TABLE
    # ------------------------------------------------------------------
    print()
    print(f"+----------------------------------------------+")
    print(f"| RESULTS: {video_id:<36}|")
    print(f"+--------------+----------+----------+--------+")
    print(f"| Method       | PSNR(dB) |  SSIM    | Time   |")
    print(f"+--------------+----------+----------+--------+")
    print(f"| Tensor RPCA  |  {mean_psnr_t:>6.2f}  |  {mean_ssim_t:.4f}  | {tensor_time:>4}s  |")
    print(f"| SS-RTD       |  {mean_psnr_s:>6.2f}  |  {mean_ssim_s:.4f}  | {ssrtd_time:>4}s  |")
    print(f"| Hybrid       |  {mean_psnr_h:>6.2f}  |  {mean_ssim_h:.4f}  | {hybrid_time:>4}s  |")
    print(f"+--------------+----------+----------+--------+")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPCA Hybrid Pipeline")
    parser.add_argument("--video_id", type=str, required=True,
                        help="Short video ID e.g. video_39")
    parser.add_argument("--video_dir", type=str, required=True,
                        help="Path to folder containing VIRAT videos")
    args = parser.parse_args()

    registry_path = PROJECT_DIR / "video_registry.csv"
    df = pd.read_csv(registry_path)
    row = df[df["short_id"] == args.video_id]
    if row.empty:
        print(f"ERROR: {args.video_id} not found in registry")
        sys.exit(1)

    filename = row.iloc[0]["original_filename"]
    video_path = Path(args.video_dir) / filename
    if not video_path.exists():
        print(f"ERROR: Video not found at {video_path}")
        sys.exit(1)

    # Only the metrics CSV is a permanent per-video output now; component and
    # compression artifacts are transient, so don't pre-create their folders.
    (RESULTS_DIR / "metrics").mkdir(parents=True, exist_ok=True)

    print(f"\nStarting pipeline for {args.video_id} ({filename})")
    print(f"Video path: {video_path}\n")

    results = process_video(args.video_id, video_path)
    print(f"\nPipeline complete for {args.video_id}")
