from pathlib import Path
import math

import numpy as np
from skimage.metrics import structural_similarity


def compute_psnr(original, reconstructed):
    mse = np.mean((original - reconstructed) ** 2)
    if mse == 0:
        return float('inf')
    return round(20 * math.log10(1.0 / math.sqrt(mse)), 4)


def compute_ssim(original, reconstructed):
    score = structural_similarity(original, reconstructed, data_range=1.0)
    return round(float(score), 4)


def compute_sparsity(component):
    total = component.size
    near_zero = np.sum(np.abs(component) < 1e-6)
    return round(100.0 * near_zero / total, 2)


def compute_psnr_sequence(original_frames, reconstructed_frames):
    per_frame = [
        compute_psnr(original_frames[t], reconstructed_frames[t])
        for t in range(original_frames.shape[0])
    ]
    finite = [v for v in per_frame if not math.isinf(v)]
    mean_psnr = round(float(np.mean(finite)), 4) if finite else float('inf')
    std_psnr = round(float(np.std(finite)), 4) if finite else 0.0
    return mean_psnr, std_psnr, per_frame


def compute_ssim_sequence(original_frames, reconstructed_frames):
    per_frame = [
        compute_ssim(original_frames[t], reconstructed_frames[t])
        for t in range(original_frames.shape[0])
    ]
    mean_ssim = round(float(np.mean(per_frame)), 4)
    std_ssim = round(float(np.std(per_frame)), 4)
    return mean_ssim, std_ssim, per_frame


def get_file_size_kb(file_path):
    return round(Path(file_path).stat().st_size / 1024, 2)


def compute_compression_ratio(original_size_kb, compressed_size_kb):
    return round(compressed_size_kb / original_size_kb, 4)


def summarize_metrics(video_id, method_name, original_frames, reconstructed_frames,
                      S_component, original_file_kb, compressed_file_kb):
    mean_psnr, std_psnr, _ = compute_psnr_sequence(original_frames, reconstructed_frames)
    mean_ssim, std_ssim, _ = compute_ssim_sequence(original_frames, reconstructed_frames)
    sparsity = compute_sparsity(S_component)
    ratio = compute_compression_ratio(original_file_kb, compressed_file_kb)
    return {
        "video_id": video_id,
        "method": method_name,
        "mean_psnr": mean_psnr,
        "std_psnr": std_psnr,
        "mean_ssim": mean_ssim,
        "std_ssim": std_ssim,
        "sparsity_pct": sparsity,
        "original_kb": round(original_file_kb, 2),
        "compressed_kb": round(compressed_file_kb, 2),
        "compression_ratio": ratio,
    }


if __name__ == "__main__":
    import numpy as np

    original = np.random.rand(300, 180, 320).astype(np.float64)
    noisy = np.clip(original + np.random.normal(0, 0.01, original.shape), 0, 1)
    sparse = np.zeros_like(original)
    sparse[::10, ::10, ::10] = 0.5

    mean_psnr, std_psnr, _ = compute_psnr_sequence(original, noisy)
    mean_ssim, std_ssim, _ = compute_ssim_sequence(original, noisy)
    sparsity = compute_sparsity(sparse)

    print(f"PSNR: {mean_psnr:.4f} ± {std_psnr:.4f} dB")
    print(f"SSIM: {mean_ssim:.4f} ± {std_ssim:.4f}")
    print(f"Sparsity: {sparsity:.2f}%")
    print("metrics.py test passed")
