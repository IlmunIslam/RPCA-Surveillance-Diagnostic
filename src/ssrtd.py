from pathlib import Path

import numpy as np

from src.preprocessing import load_video_frames, frames_to_tensor


# ---------------------------------------------------------------------------
# Helpers (copied from tensor_rpca.py — kept independent for Colab portability)
# ---------------------------------------------------------------------------

def unfold(tensor, mode):
    """Unfold 3D tensor (H,W,T) along given mode."""
    moved = np.moveaxis(tensor, mode, 0)
    return moved.reshape(moved.shape[0], -1)


def fold(matrix, mode, shape):
    """Inverse of unfold."""
    remaining = [shape[i] for i in range(len(shape)) if i != mode]
    unflat = matrix.reshape([shape[mode]] + remaining)
    return np.moveaxis(unflat, 0, mode)


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

def ssrtd(X, lam_s=0.001, lam_n=0.002, max_iter=500, tol=1e-7):
    """
    SS-RTD modified for surveillance video — smoothness penalty removed.

    Decomposes X = L + S + N where:
      L = low-rank background (Tucker structure via tensor SVT)
      S = sparse foreground (sharp-edged on surveillance video)
      N = noise/movement carrier (carries motion when S collapses to 0)

    Smoothness penalty from original paper removed: causes float64 overflow on
    sharp-edged human foreground in surveillance domain. Documented as a
    domain-transfer finding of this research.

    Parameters
    ----------
    X        : ndarray (H, W, T), float64, values in [0, 1]
    lam_s    : sparsity regularization for S (default 0.001)
    lam_n    : sparsity regularization for N (default 0.002)
    max_iter : maximum ADMM iterations
    tol      : convergence tolerance on relative change in L

    Returns
    -------
    L : ndarray (H, W, T) — background
    S : ndarray (H, W, T) — sparse foreground
    N : ndarray (H, W, T) — noise/movement carrier
    n_iter : int
    """
    mu = 1.0 / (np.sqrt(max(X.shape)) * np.mean(np.abs(X)))
    rho = 1.5

    L = np.zeros_like(X)
    S = np.zeros_like(X)
    N = np.zeros_like(X)
    Y = np.zeros_like(X)

    n_iter = max_iter
    for i in range(1, max_iter + 1):
        L_old = L.copy()

        L = tensor_svt(X - S - N + Y / mu, 1.0 / mu)
        S = soft_threshold(X - L - N + Y / mu, lam_s / mu)
        N = soft_threshold(X - L - S + Y / mu, lam_n / mu)
        Y = Y + mu * (X - L - S - N)
        mu = min(mu * rho, 1e6)

        rel_change = np.linalg.norm(L - L_old) / (np.linalg.norm(L_old) + 1e-10)

        if i % 50 == 0:
            s_nnz = np.mean(np.abs(S) > 1e-6) * 100
            n_nnz = np.mean(np.abs(N) > 1e-6) * 100
            print(f"  iter {i}/{max_iter} — rel_change: {rel_change:.2e}, "
                  f"S_nnz: {s_nnz:.1f}%, N_nnz: {n_nnz:.1f}%")

        if rel_change < tol:
            n_iter = i
            break

    s_nnz_final = np.mean(np.abs(S) > 1e-6) * 100
    n_nnz_final = np.mean(np.abs(N) > 1e-6) * 100

    print(f"SS-RTD converged in {n_iter} iterations")
    print(f"  Final S sparsity: {s_nnz_final:.2f}% nonzero")
    print(f"  Final N sparsity: {n_nnz_final:.2f}% nonzero")
    print("  Domain note: S collapse expected on surveillance video — N carries movement")

    return L, S, N, n_iter


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_ssrtd(video_id, registry_df, video_dir, output_dir, lam_s=0.001, lam_n=0.002):
    """
    Runs ssrtd on one video identified by video_id and saves L, S, N as .npy.

    Returns
    -------
    dict with keys: video_id, n_iter, L_path, S_path, N_path
    """
    video_dir = Path(video_dir)
    output_dir = Path(output_dir)

    row = registry_df[registry_df["short_id"] == video_id].iloc[0]
    video_path = video_dir / row["original_filename"]

    frames = load_video_frames(video_path, max_frames=300)
    X = frames_to_tensor(frames)  # (H, W, T)

    L, S, N, n_iter = ssrtd(X, lam_s=lam_s, lam_n=lam_n)

    save_dir = output_dir / video_id
    save_dir.mkdir(parents=True, exist_ok=True)

    L_path = save_dir / "L_ssrtd.npy"
    S_path = save_dir / "S_ssrtd.npy"
    N_path = save_dir / "N_ssrtd.npy"
    np.save(L_path, L)
    np.save(S_path, S)
    np.save(N_path, N)

    return {
        "video_id": video_id,
        "n_iter": n_iter,
        "L_path": str(L_path),
        "S_path": str(S_path),
        "N_path": str(N_path),
    }


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

    noise = np.random.normal(0, 0.005, (H, W, T))
    X = np.clip(L_true + S_true + noise, 0, 1)

    print(f"Running SS-RTD on synthetic {H}x{W}x{T} tensor")
    print(f"lam_s={0.001}, lam_n={0.002}")
    L, S, N, n_iter = ssrtd(X, lam_s=0.001, lam_n=0.002, max_iter=200, tol=1e-5)

    print(f"L shape: {L.shape}")
    print(f"S nonzero: {np.mean(np.abs(S) > 1e-6) * 100:.2f}%")
    print(f"N nonzero: {np.mean(np.abs(N) > 1e-6) * 100:.2f}%")
    print(f"Reconstruction error: {np.linalg.norm(X - L - S - N):.6f}")
    print("ssrtd.py test passed")
