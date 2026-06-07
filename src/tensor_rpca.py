from pathlib import Path

import numpy as np

from src.preprocessing import load_video_frames, frames_to_tensor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unfold(tensor, mode):
    """Unfold 3D tensor (H,W,T) along given mode."""
    moved = np.moveaxis(tensor, mode, 0)          # bring mode-axis to front
    return moved.reshape(moved.shape[0], -1)       # (dim_mode, rest)


def fold(matrix, mode, shape):
    """Inverse of unfold — reshape matrix back to original tensor shape."""
    # shape is the original (H, W, T)
    # after moveaxis(mode→0) the order is (shape[mode], *remaining)
    remaining = [shape[i] for i in range(len(shape)) if i != mode]
    unflat = matrix.reshape([shape[mode]] + remaining)   # (dim_mode, *rest)
    return np.moveaxis(unflat, 0, mode)                  # restore original axis order


def soft_threshold(X, threshold):
    return np.sign(X) * np.maximum(np.abs(X) - threshold, 0)


def tensor_svt(X, threshold):
    """SVT along each mode; average the three refold results."""
    shape = X.shape
    results = []
    for mode in range(3):
        M = unfold(X, mode)
        U, sigma, Vt = np.linalg.svd(M, full_matrices=False)
        sigma_thresh = np.maximum(sigma - threshold, 0)
        M_thresh = U @ np.diag(sigma_thresh) @ Vt
        results.append(fold(M_thresh, mode, shape))
    return (results[0] + results[1] + results[2]) / 3.0


# ---------------------------------------------------------------------------
# Main algorithm
# ---------------------------------------------------------------------------

def tensor_rpca(X, lam=None, max_iter=500, tol=1e-7):
    """
    Tensor RPCA via ADMM on the t-SVD framework.
    Decomposes X = L + S where L is low-rank and S is sparse.

    Parameters
    ----------
    X        : ndarray (H, W, T), float64, values in [0, 1]
    lam      : regularization weight (default 1/sqrt(max(H,W)))
    max_iter : maximum ADMM iterations
    tol      : convergence tolerance on relative change in L

    Returns
    -------
    L : ndarray (H, W, T) — background
    S : ndarray (H, W, T) — foreground
    n_iter : int
    """
    if lam is None:
        lam = 1.0 / np.sqrt(max(X.shape[0], X.shape[1]))

    mu = 1.0 / (np.sqrt(max(X.shape)) * np.mean(np.abs(X)))
    rho = 1.5

    L = np.zeros_like(X)
    S = np.zeros_like(X)
    Y = np.zeros_like(X)

    n_iter = max_iter
    for i in range(1, max_iter + 1):
        L_old = L.copy()

        L = tensor_svt(X - S + Y / mu, 1.0 / mu)
        S = soft_threshold(X - L + Y / mu, lam / mu)
        Y = Y + mu * (X - L - S)
        mu = min(mu * rho, 1e6)

        rel_change = np.linalg.norm(L - L_old) / (np.linalg.norm(L_old) + 1e-10)

        if i % 50 == 0:
            print(f"  iter {i}/{max_iter} — rel_change: {rel_change:.2e}")

        if rel_change < tol:
            n_iter = i
            break

    print(f"Tensor RPCA converged in {n_iter} iterations")
    return L, S, n_iter


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tensor_rpca(video_id, registry_df, video_dir, output_dir, lam=None):
    """
    Runs tensor_rpca on one video identified by video_id and saves L, S as .npy.

    Returns
    -------
    dict with keys: video_id, n_iter, L_path, S_path
    """
    video_dir = Path(video_dir)
    output_dir = Path(output_dir)

    row = registry_df[registry_df["short_id"] == video_id].iloc[0]
    video_path = video_dir / row["original_filename"]

    frames = load_video_frames(video_path, max_frames=300)
    X = frames_to_tensor(frames)  # (H, W, T)

    L, S, n_iter = tensor_rpca(X, lam=lam)

    save_dir = output_dir / video_id
    save_dir.mkdir(parents=True, exist_ok=True)

    L_path = save_dir / "L_tensor.npy"
    S_path = save_dir / "S_tensor.npy"
    np.save(L_path, L)
    np.save(S_path, S)

    return {"video_id": video_id, "n_iter": n_iter, "L_path": str(L_path), "S_path": str(S_path)}


# ---------------------------------------------------------------------------
# Quick synthetic test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    H, W, T = 10, 10, 20

    U = np.random.randn(H, 2)
    V = np.random.randn(W, 2)
    t = np.random.randn(T, 2)
    L_true = np.einsum('hi,wi,ti->hwt', U, V, t) * 0.1
    L_true = (L_true - L_true.min()) / (L_true.max() - L_true.min()) * 0.8

    S_true = np.zeros((H, W, T))
    idx = np.random.choice(H * W * T, size=int(0.05 * H * W * T), replace=False)
    S_true.flat[idx] = np.random.uniform(0.1, 0.3, len(idx))

    X = np.clip(L_true + S_true, 0, 1)

    lam = 1.0 / np.sqrt(max(H, W))
    print(f"Running tensor_rpca on synthetic {H}x{W}x{T} tensor, lam={lam:.4f}")
    L, S, n_iter = tensor_rpca(X, lam=lam, max_iter=200, tol=1e-5)

    print(f"L shape: {L.shape}, S shape: {S.shape}")
    print(f"L range: [{L.min():.4f}, {L.max():.4f}]")
    print(f"S sparsity: {np.mean(np.abs(S) < 1e-6) * 100:.1f}%")
    print("tensor_rpca.py test passed")
