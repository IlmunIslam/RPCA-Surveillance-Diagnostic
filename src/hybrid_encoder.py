from pathlib import Path

import cv2
import numpy as np


def build_hybrid(L_tensor, N_ssrtd):
    """
    Combines Tensor RPCA background with SS-RTD movement carrier.

    Parameters
    ----------
    L_tensor : ndarray (H, W, T) — from tensor_rpca output
    N_ssrtd  : ndarray (H, W, T) — from ssrtd output

    Returns
    -------
    hybrid : ndarray (H, W, T), clipped to [0, 1]
    """
    if L_tensor.shape != N_ssrtd.shape:
        raise ValueError(
            f"Shape mismatch: L_tensor {L_tensor.shape} vs N_ssrtd {N_ssrtd.shape}"
        )

    hybrid = np.clip(L_tensor + N_ssrtd, 0, 1)
    print(f"Built hybrid: shape {hybrid.shape}, range [{hybrid.min():.4f}, {hybrid.max():.4f}]")
    return hybrid


def hybrid_to_frames(hybrid):
    """
    Converts hybrid tensor (H, W, T) to frames array (T, H, W).
    """
    return np.transpose(hybrid, (2, 0, 1))


def save_video_mp4(frames, output_path, fps=25.0):
    """
    Saves frames array (T, H, W), values in [0, 1], as MP4 via OpenCV.
    """
    output_path = Path(output_path)
    T, H, W = frames.shape

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (W, H))

    for t in range(T):
        frame_uint8 = (frames[t] * 255).clip(0, 255).astype(np.uint8)
        frame_bgr = cv2.cvtColor(frame_uint8, cv2.COLOR_GRAY2BGR)
        writer.write(frame_bgr)

    writer.release()
    print(f"Saved video to {output_path} ({T} frames, {fps} fps)")


def run_hybrid(video_id, tensor_rpca_dir, ssrtd_dir, output_dir):
    """
    Loads pre-computed L_tensor and N_ssrtd, builds hybrid, saves results.

    Returns
    -------
    dict with keys: video_id, hybrid_path, npy_path, shape
    """
    tensor_rpca_dir = Path(tensor_rpca_dir)
    ssrtd_dir = Path(ssrtd_dir)
    output_dir = Path(output_dir)

    L_tensor = np.load(tensor_rpca_dir / video_id / "L_tensor.npy")
    N_ssrtd = np.load(ssrtd_dir / video_id / "N_ssrtd.npy")

    hybrid = build_hybrid(L_tensor, N_ssrtd)
    frames = hybrid_to_frames(hybrid)

    save_dir = output_dir / video_id
    save_dir.mkdir(parents=True, exist_ok=True)

    video_path = save_dir / "hybrid_reconstructed.mp4"
    npy_path = save_dir / "hybrid.npy"

    save_video_mp4(frames, video_path)
    np.save(npy_path, hybrid)

    return {
        "video_id": video_id,
        "hybrid_path": str(video_path),
        "npy_path": str(npy_path),
        "shape": hybrid.shape,
    }


if __name__ == "__main__":
    H, W, T = 180, 320, 300

    L = np.ones((H, W, T)) * 0.5
    L += np.random.normal(0, 0.02, (H, W, T))
    L = np.clip(L, 0, 1)

    N = np.zeros((H, W, T))
    for t in range(T):
        n_active = int(0.03 * H * W)
        idx = np.random.choice(H * W, n_active, replace=False)
        N.reshape(H * W, T)[idx, t] = np.random.uniform(0.1, 0.4, n_active)

    hybrid = build_hybrid(L, N)
    frames = hybrid_to_frames(hybrid)

    print(f"hybrid shape: {hybrid.shape}")
    print(f"frames shape: {frames.shape}")
    print(f"frames dtype: {frames.dtype}")
    print(f"frames range: [{frames.min():.4f}, {frames.max():.4f}]")
    assert hybrid.shape == (H, W, T), "Wrong hybrid shape"
    assert frames.shape == (T, H, W), "Wrong frames shape"
    assert frames.min() >= 0.0 and frames.max() <= 1.0, "Values out of range"
    print("hybrid_encoder.py test passed")
