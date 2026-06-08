import shutil
import subprocess
from pathlib import Path

import numpy as np

from src.preprocessing import load_video_frames
from src.metrics import compute_psnr_sequence, compute_ssim_sequence, get_file_size_kb

# Locate ffmpeg: prefer PATH, fall back to known WinGet install location
_FFMPEG = shutil.which("ffmpeg") or r"C:\Users\ilmun\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"


def encode_frames_h264(frames, output_path, crf=23, fps=25.0):
    """
    Encodes numpy frames (T, H, W), float64 [0,1] as H.264 MP4 via ffmpeg subprocess.
    """
    output_path = Path(output_path)
    T, H, W = frames.shape

    frames_uint8 = (frames * 255).clip(0, 255).astype(np.uint8)

    cmd = [
        _FFMPEG, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "gray",
        "-r", str(fps),
        "-i", "pipe:0",
        "-vcodec", "libx264",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.stdin.write(frames_uint8.tobytes())
    proc.stdin.close()
    proc.wait()

    return output_path


def decode_h264_to_frames(video_path, max_frames=300):
    """
    Decodes H.264 MP4 back to numpy array (T, H, W), float64, values [0,1].
    """
    return load_video_frames(video_path, max_frames=max_frames)


def measure_compression(frames_original, label, output_dir, crf=28, fps=25.0):
    """
    Encodes at crf=23 (reference) and crf=28 (compressed), measures file sizes
    and PSNR/SSIM of decoded compressed vs original.
    """
    output_dir = Path(output_dir)

    ref_path = output_dir / f"{label}_crf23.mp4"
    comp_path = output_dir / f"{label}_crf28.mp4"

    encode_frames_h264(frames_original, ref_path, crf=23, fps=fps)
    reference_kb = get_file_size_kb(ref_path)

    encode_frames_h264(frames_original, comp_path, crf=crf, fps=fps)
    compressed_kb = get_file_size_kb(comp_path)

    decoded = decode_h264_to_frames(comp_path, max_frames=frames_original.shape[0])

    # Align frame counts in case decoder returns slightly fewer frames
    T = min(frames_original.shape[0], decoded.shape[0])
    mean_psnr, _, _ = compute_psnr_sequence(frames_original[:T], decoded[:T])
    mean_ssim, _, _ = compute_ssim_sequence(frames_original[:T], decoded[:T])

    return {
        "label": label,
        "reference_kb": round(reference_kb, 2),
        "compressed_kb": round(compressed_kb, 2),
        "compression_ratio": round(compressed_kb / reference_kb, 4) if reference_kb > 0 else 0.0,
        "psnr_after_h264": mean_psnr,
        "ssim_after_h264": mean_ssim,
    }


def run_compression_analysis(video_id, original_frames,
                              L_tensor, S_tensor,
                              L_ssrtd, S_ssrtd, N_ssrtd,
                              hybrid_frames, output_dir):
    """
    Runs compression measurement on all components and prints a comparison table.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert tensors (H, W, T) to frames (T, H, W)
    def to_frames(tensor):
        return np.transpose(tensor, (2, 0, 1))

    components = [
        ("original", original_frames),
        ("L_tensor", to_frames(L_tensor)),
        ("S_tensor", to_frames(S_tensor)),
        ("N_ssrtd",  to_frames(N_ssrtd)),
        ("hybrid",   hybrid_frames),
    ]

    results = []
    for label, frames in components:
        r = measure_compression(frames, label, output_dir)
        results.append(r)

    # Print table
    sep = "+------------+--------------+---------------+-------+--------+"
    hdr = "| Component  | Ref size(KB) | Comp size(KB) | Ratio | PSNR   |"
    print(sep)
    print(hdr)
    print(sep)
    for r in results:
        print(
            f"| {r['label']:<10} | {r['reference_kb']:>12.2f} | "
            f"{r['compressed_kb']:>13.2f} | {r['compression_ratio']:>5.3f} | "
            f"{r['psnr_after_h264']:>6.2f} |"
        )
    print(sep)

    return results


if __name__ == "__main__":
    import numpy as np
    from pathlib import Path

    T, H, W = 30, 180, 320
    frames = np.random.rand(T, H, W).astype(np.float64) * 0.8 + 0.1

    test_dir = Path("results/compression_test")
    test_dir.mkdir(parents=True, exist_ok=True)

    result = measure_compression(frames, "test", test_dir, crf=28)
    print(f"Reference size: {result['reference_kb']:.2f} KB")
    print(f"Compressed size: {result['compressed_kb']:.2f} KB")
    print(f"Compression ratio: {result['compression_ratio']:.4f}")
    print(f"PSNR after H.264: {result['psnr_after_h264']:.2f} dB")
    print(f"SSIM after H.264: {result['ssim_after_h264']:.4f}")
    print("compression.py test passed")
