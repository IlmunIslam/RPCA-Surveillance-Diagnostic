from pathlib import Path

import numpy as np

from src.hybrid_encoder import build_hybrid, hybrid_to_frames
from src.compression import measure_compression

PROJECT_DIR = Path(__file__).parent.parent
RESULTS = PROJECT_DIR / "results"
COMP_DIR = RESULTS / "compression" / "video_39_recheck"
COMP_DIR.mkdir(parents=True, exist_ok=True)

# 1 & 2. Load existing arrays
L_tensor = np.load(RESULTS / "tensor_rpca" / "video_39" / "L_tensor.npy")
N_ssrtd  = np.load(RESULTS / "ssrtd"       / "video_39" / "N_ssrtd.npy")

# 3. N_ssrtd stats
print("N_ssrtd stats:")
print(f"  shape   : {N_ssrtd.shape}")
print(f"  min     : {N_ssrtd.min():.6f}")
print(f"  max     : {N_ssrtd.max():.6f}")
print(f"  nonzero : {np.mean(np.abs(N_ssrtd) > 1e-6)*100:.4f}%")

# 4. L_tensor stats
print("\nL_tensor stats:")
print(f"  shape   : {L_tensor.shape}")
print(f"  min     : {L_tensor.min():.6f}")
print(f"  max     : {L_tensor.max():.6f}")
print(f"  nonzero : {np.mean(np.abs(L_tensor) > 1e-6)*100:.4f}%")

# 5. Build hybrid
hybrid = build_hybrid(L_tensor, N_ssrtd)

# 6. Convert to frames (T, H, W)
L_frames      = np.transpose(L_tensor, (2, 0, 1))
hybrid_frames = hybrid_to_frames(hybrid)

# 7. Compression
print("\nRunning compression (CRF=28)...")
r_L      = measure_compression(L_frames,      "L_tensor", COMP_DIR, crf=28)
r_hybrid = measure_compression(hybrid_frames, "hybrid",   COMP_DIR, crf=28)

# 8. Side-by-side comparison
print()
print("+------------+--------------+---------------+-------+--------+--------+")
print("| Component  | Ref size(KB) | Comp size(KB) | Ratio | PSNR   | SSIM   |")
print("+------------+--------------+---------------+-------+--------+--------+")
for r in [r_L, r_hybrid]:
    print(
        f"| {r['label']:<10} | {r['reference_kb']:>12.2f} | "
        f"{r['compressed_kb']:>13.2f} | {r['compression_ratio']:>5.3f} | "
        f"{r['psnr_after_h264']:>6.2f} | {r['ssim_after_h264']:>6.4f} |"
    )
print("+------------+--------------+---------------+-------+--------+--------+")
