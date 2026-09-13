"""
Real SS-RTD — faithful implementation of Shen et al. 2022.

    B. Shen, R. R. Kamath, H. Choo, Z. Kong, "Robust Tensor Decomposition based
    Background/Foreground Separation in Noisy Videos and Its Applications in
    Additive Manufacturing," IEEE Trans. Automation Science and Engineering,
    vol. 20, no. 1, pp. 583-596, 2022. DOI 10.1109/TASE.2022.3163674

Verified equations are transcribed in paper/SOURCE.md. Equation numbers in the
docstrings below refer to the published article.

This is NOT src/ssrtd.py. That module is the naive three-component baseline
(low-rank via SVT + two independent soft-thresholded components); it is not
SS-RTD and not a variant of it. See ARCHIVE_BASELINE.md.

Build status (see IMPLEMENTATION_PLAN.md):
    (a) TV difference operators + Phi precompute   -- this file, below
    (b) Tucker / HOOI low-rank solver for L        -- this file, below
    (c) S-update via 3D FFT                        -- this file, below
    (d) f-update (TV auxiliary)                    -- this file, below
    (e) E-update (sparse noise)                    -- not yet built
    (f) Multiplier + adaptive penalty updates      -- not yet built
    (g) Full ADMM assembly (Algorithm 1)           -- not yet built
"""

import numpy as np

# Reuse the repo's existing helpers rather than adding another copy;
# tensor_rpca.py and ssrtd.py already define these. soft_threshold there is
# character-for-character the paper's definition,
# soft(A, tau) = sign(A) * max(|A| - tau, 0), used by both (d) and (e).
from src.tensor_rpca import unfold, fold, soft_threshold

# Axis convention. Tensors are (H, W, T): axis 0 = height, 1 = width, 2 = time.
#
# The paper defines the three difference operators on S(x, y, t) as
#     Sh(x, y, t) = S(x + 1, y, t) - S(x, y, t)     -> axis 0
#     Sv(x, y, t) = S(x, y + 1, t) - S(x, y, t)     -> axis 1
#     St(x, y, t) = S(x, y, t + 1) - S(x, y, t)     -> axis 2
# and calls them "horizontal, vertical and temporal" respectively. Note that
# the operator the paper names "horizontal" differences along x, which indexes
# HEIGHT in our (H, W, T) layout. That naming is the paper's, not a bug here,
# and it is numerically irrelevant: both the TV1 norm (eq. 4) and Phi (eq. 9)
# sum symmetrically over all three operators, so relabelling h and v changes
# nothing. Do not "fix" it.
_AXES = (0, 1, 2)


def tv_forward(S):
    """
    Apply the three difference operators, stacked: D vec(S) in the paper's terms.

    Forward differences with PERIODIC boundary conditions, so each operator is
    circulant -- which is what makes the FFT solve of eq. (9) valid. Implemented
    with np.roll rather than np.diff: np.diff would shorten the array and give
    non-periodic edges, i.e. a different (non-circulant) operator.

    S : (H, W, T) array
    -> (3, H, W, T) array, index 0/1/2 = Dh/Dv/Dt
    """
    S = np.asarray(S)
    return np.stack([np.roll(S, -1, axis=ax) - S for ax in _AXES], axis=0)


def tv_adjoint(Z):
    """
    Apply the adjoint D*, mapping the stacked triple back to a single tensor.

    For the circular forward difference D_k x = roll(x, -1, axis=k) - x,

        <D_k x, y> = sum_i (x[i+1] - x[i]) y[i]
                   = sum_j x[j] y[j-1] - sum_i x[i] y[i]     (reindex, periodic)
                   = <x, roll(y, +1, axis=k) - y>

    so the adjoint of each operator is the backward difference, negated. The
    adjoint of the stacked D is the sum of the three component adjoints.

    Z : (3, H, W, T) array
    -> (H, W, T) array
    """
    Z = np.asarray(Z)
    return sum(np.roll(Z[i], +1, axis=ax) - Z[i] for i, ax in enumerate(_AXES))


def tv_norm(S):
    """
    Anisotropic total variation norm, eq. (4):

        ||S||_TV1 = sum_i ( |[Dh s]_i| + |[Dv s]_i| + |[Dt s]_i| )

    i.e. the l1 norm of the stacked difference operators.

    S : (H, W, T) array
    -> float
    """
    return float(np.abs(tv_forward(S)).sum())


def compute_phi(shape):
    """
    Precompute Phi = |fftn(Dh)|^2 + |fftn(Dv)|^2 + |fftn(Dt)|^2, the eigenvalue
    array of D*D under the 3D DFT. Used in the denominator of eq. (9):

        S = ifftn( fftn(C) / (beta_X * 1 + beta_f * Phi) )

    Phi depends only on the tensor shape -- not on the data or any model
    parameter -- so it is computed once per run.

    Derived from the operator itself rather than a hand-written kernel: for a
    circulant operator A, the DFT eigenvalues are fftn(A applied to a unit
    impulse at the origin). Building Phi this way keeps it consistent with
    tv_forward by construction; a hand-written kernel could carry a sign or
    off-by-one error that |.|^2 would hide, surfacing only as a wrong S in the
    eq. (9) solve.

    shape : (H, W, T)
    -> (H, W, T) real non-negative array
    """
    delta = np.zeros(shape, dtype=np.float64)
    delta[0, 0, 0] = 1.0
    D_delta = tv_forward(delta)
    return sum(np.abs(np.fft.fftn(D_delta[i])) ** 2 for i in range(3))


# ===========================================================================
# (b) Tucker / HOOI low-rank solver for L -- eq. (3), (8)
# ===========================================================================
#
# eq. (3):  L = G x1 U1 x2 U2 x3 U3,  Uj orthonormal in columns
# eq. (8):  min_{G,Uj} ||X_tilde - G x1 U1 x2 U2 x3 U3||_F^2  s.t. Uj^T Uj = I
#           where X_tilde = X - S - E - Lambda_X / beta_X
#
# Solved by HOOI (paper's ref [13] = Kolda & Bader, "Tensor decompositions and
# applications", SIAM Review 51(3):455-500, 2009). The paper runs 20 inner
# iterations (III-C complexity analysis). HOOI is non-convex and is not
# guaranteed to reach a global optimum, but its objective is monotonically
# non-increasing -- which test_hooi.py checks.


def tucker_ranks(shape, frac=0.8):
    """
    Multilinear ranks per Algorithm 1 / III-C: r1 = ceil(0.8H), r2 = ceil(0.8W),
    r3 = 1.

    r3 = 1 forces the mode-3 unfolding of L to rank 1, so every frame of L is a
    scalar multiple of one common spatial image. The paper describes this as
    "each image frame in L is the same"; strictly the frames are proportional,
    identical only when the temporal factor is constant. See test_hooi.py.

    frac is exposed for testing only -- the paper fixes it at 0.8.
    """
    H, W, T = shape
    # 0.8 is not exactly representable in binary; clamp so a float-repr surprise
    # can never produce r > dim and a cryptic SVD failure downstream.
    r1 = min(int(np.ceil(frac * H)), H)
    r2 = min(int(np.ceil(frac * W)), W)
    r3 = min(1, T)
    return (r1, r2, r3)


def feasible_ranks(shape, ranks):
    """
    Clamp requested multilinear ranks to what a Tucker model can actually attain.

    A rank triple is attainable only if r_k <= prod_{j != k} r_j, because the
    mode-k unfolding of L = G x1 U1 x2 U2 x3 U3 is U_k G_(k) (...)^T, whose rank
    cannot exceed the product of the other two ranks. Requesting more simply
    yields a factor with fewer columns than asked for.

    NOTE ON THE PAPER'S RANK RULE. With r3 = 1 the condition becomes
    r1 <= r2 and r2 <= r1, i.e. **r1 must equal r2**. The paper's rule
    r1 = ceil(0.8H), r2 = ceil(0.8W), r3 = 1 therefore over-specifies r2
    whenever H != W: for our (180, 320, 300) tensors it asks for
    (144, 256, 1) but only (144, 144, 1) is attainable, and for the paper's own
    Candela data (288 x 352) it asks for (231, 282, 1) against an attainable
    (231, 231, 1). This is inherent to the model, not to this implementation:
    with r3 = 1 every frame of L is a multiple of one H x W image, and that
    image has rank at most min(r1, r2). Clamping makes the effective model
    explicit rather than letting factors come back silently short.
    """
    r = [min(ranks[k], shape[k]) for k in range(3)]
    for _ in range(3):                       # iterate to a fixed point
        for k in range(3):
            other = 1
            for j in range(3):
                if j != k:
                    other *= r[j]
            r[k] = min(r[k], other)
    return tuple(r)


def mode_dot(tensor, matrix, mode):
    """tensor x_mode matrix, where matrix is (out_dim, tensor.shape[mode])."""
    new_shape = list(tensor.shape)
    new_shape[mode] = matrix.shape[0]
    return fold(matrix @ unfold(tensor, mode), mode, tuple(new_shape))


def _leading_left_singvecs(M, r, use_gram=None):
    """
    Top-r left singular vectors of M.

    For very wide unfoldings (the mode-2 case here is 300 x 36864) a full SVD
    computes tens of thousands of right singular vectors that are then thrown
    away. The Gram route -- eigendecomposition of the small M M^T -- returns the
    same left subspace at a fraction of the cost. It squares the condition
    number, which is acceptable here because only the leading, well-separated
    directions are wanted.
    """
    n, m = M.shape
    if use_gram is None:
        use_gram = m > 4 * n
    if use_gram:
        w, V = np.linalg.eigh(M @ M.T)          # ascending eigenvalues
        return np.ascontiguousarray(V[:, ::-1][:, :r])
    U, _, _ = np.linalg.svd(M, full_matrices=False)
    return U[:, :r]


def _contract_others(X, Us, skip, ranks):
    """
    X x_j Uj^T for every mode j != skip.

    Order matters a great deal. Contracting the mode that shrinks most first
    keeps every later contraction small: with r3 = 1 the time axis collapses
    300 -> 1 for ~17M flops, after which the remaining work is trivial. The
    reverse order does the same job for billions of flops.
    """
    others = sorted((j for j in range(3) if j != skip),
                    key=lambda j: ranks[j] / X.shape[j])
    Y = X
    for j in others:
        Y = mode_dot(Y, Us[j].T, j)
    return Y


def hosvd_init(X, ranks):
    """HOSVD initialization: leading r_k left singular vectors of each unfolding."""
    return [_leading_left_singvecs(unfold(X, k), ranks[k]) for k in range(3)]


def tucker_core(X, Us):
    """G = X x1 U1^T x2 U2^T x3 U3^T."""
    G = X
    for k in range(3):
        G = mode_dot(G, Us[k].T, k)
    return G


def tucker_reconstruct(G, Us):
    """L = G x1 U1 x2 U2 x3 U3 -- eq. (3)."""
    L = G
    for k in range(3):
        L = mode_dot(L, Us[k], k)
    return L


def hooi(X, ranks=None, n_iter=20, return_history=False):
    """
    Solve eq. (8) by higher-order orthogonal iteration.

    X       : (H, W, T) array -- X_tilde at call sites inside the ADMM
    ranks   : (r1, r2, r3); defaults to tucker_ranks(X.shape)
    n_iter  : inner iterations; the paper uses 20
    -> (G, [U0, U1, U2], L), plus history when return_history is True

    Because the factors are orthonormal, L is the orthogonal projection of X
    onto the Tucker subspace, so ||X - L||_F^2 == ||X||_F^2 - ||G||_F^2. The
    history uses that identity (cheap); test_hooi.py checks it against the
    directly computed residual.
    """
    X = np.asarray(X, dtype=np.float64)
    if ranks is None:
        ranks = tucker_ranks(X.shape)
    # The paper's rank rule can request more than a Tucker model can attain
    # (see feasible_ranks). Clamp so factor shapes are what they claim to be.
    ranks = feasible_ranks(X.shape, ranks)

    Us = hosvd_init(X, ranks)
    normX2 = float(np.sum(X * X))
    history = []

    for _ in range(n_iter):
        for k in range(3):
            Y = _contract_others(X, Us, skip=k, ranks=ranks)
            Us[k] = _leading_left_singvecs(unfold(Y, k), ranks[k])

        if return_history:
            G_it = tucker_core(X, Us)
            resid2 = max(normX2 - float(np.sum(G_it * G_it)), 0.0)
            history.append({
                "error": np.sqrt(resid2),
                "rel_error": np.sqrt(resid2 / normX2) if normX2 > 0 else 0.0,
                "max_orth_err": max(
                    float(np.abs(U.T @ U - np.eye(U.shape[1])).max()) for U in Us
                ),
            })

    G = tucker_core(X, Us)
    L = tucker_reconstruct(G, Us)
    if return_history:
        return G, Us, L, history
    return G, Us, L


# ===========================================================================
# (c) S-update via 3D FFT -- eq. (9)
# ===========================================================================
#
# Setting the gradient of the augmented Lagrangian w.r.t. S to zero gives
#
#   (beta_X I + beta_f D*D) vec(S)
#     = beta_X ( vec(X) - vec(L) - vec(E) ) - vec(Lambda_X) + D*(beta_f f - lambda_f)
#
# with right-hand side C = beta_X (X - L - E) - Lambda_X + ten(D*(beta_f f - lambda_f)).
# D*D is block-circulant, so it is diagonalized by the 3D DFT and S follows in
# closed form:
#
#   S = ifftn( fftn(C) / (beta_X * 1 + beta_f * Phi) )                    (9)


def update_S(X, L, E, mult_X, f, mult_f, beta_X, beta_f, phi=None,
             return_info=False):
    """
    Closed-form S-update, eq. (9).

    X, L, E, mult_X : (H, W, T)      -- data, low-rank, sparse, and Lambda_X
    f, mult_f       : (3, H, W, T)   -- TV auxiliary and its multiplier lambda_f
    beta_X, beta_f  : positive scalars
    phi             : (H, W, T) from compute_phi; computed here if omitted, but
                      the paper notes it "only needs to be calculated once in the
                      whole algorithm", so hoist it out of the ADMM loop.
    -> S, or (S, info) when return_info

    Sign convention cross-checks against eq. (8): beta_X(X - L - E) - Lambda_X
    equals beta_X * (X - L - E - Lambda_X/beta_X), and X_tilde in eq. (8) is
    X - S - E - Lambda_X/beta_X. Same convention, so a sign slip here would
    contradict (8) rather than merely look wrong.
    """
    X = np.asarray(X, dtype=np.float64)
    if phi is None:
        phi = compute_phi(X.shape)

    C = beta_X * (X - L - E) - mult_X + tv_adjoint(beta_f * f - mult_f)

    # Phi has a zero eigenvalue at the DC bin -- D*D annihilates constants -- so
    # the beta_X * 1 identity term is the only thing keeping this denominator
    # non-zero there. Dropping it puts inf/nan into S on the first iteration.
    denom = beta_X + beta_f * phi
    denom_min = float(denom.min())
    if not denom_min > 0:
        raise ValueError(
            f"eq. (9) denominator is not strictly positive (min={denom_min!r}). "
            f"beta_X must be > 0: Phi vanishes at the DC bin, so beta_X * 1 is "
            f"what keeps beta_X * 1 + beta_f * Phi invertible."
        )

    S_complex = np.fft.ifftn(np.fft.fftn(C) / denom)
    S = S_complex.real

    if return_info:
        scale = max(float(np.abs(S).max()), 1.0)
        return S, {
            "denom_min": denom_min,
            "denom_max": float(denom.max()),
            "max_imag": float(np.abs(S_complex.imag).max()),
            "max_imag_rel": float(np.abs(S_complex.imag).max()) / scale,
            "C": C,
        }
    return S


# ===========================================================================
# (d) f-update, TV auxiliary -- eq. (10), (11)
# ===========================================================================
#
# eq. (10):  min_f  lambda ||f||_q + (beta_f/2) ||f - (D vec(S) + lambda_f/beta_f)||_2^2
# eq. (11):  f = soft( D vec(S) + lambda_f/beta_f ,  lambda/beta_f )
#
# q = 1 here: Algorithm 1 line 4 reads "Updating f via (11) for anisotropic
# total variation", and the soft-threshold is applied ELEMENT-WISE over all
# 3HWT entries. Isotropic TV would instead shrink (f_h, f_v, f_t) as a group
# through a per-voxel 2-norm; (d) is the only component that would change.
#
# THE TWO LAMBDAS. Both appear in eq. (11) and they are different objects:
#
#   lambda    scalar tuning parameter, in [0.2, 1]  -> the THRESHOLD, lambda/beta_f
#   lambda_f  multiplier, shape (3, H, W, T)        -> the SHIFT,      lambda_f/beta_f
#
# In print they differ by one superscript and sit in the same expression. Swap
# them in code and NumPy raises nothing -- a scalar shift and an array threshold
# both broadcast, producing a correctly shaped, entirely wrong f, after which
# the ADMM converges to something plausible. Hence `lam` vs `mult_f` here, the
# argument ordering below, and the explicit guards.


def update_f(S, mult_f, lam, beta_f, return_info=False):
    """
    Closed-form f-update, eq. (11) -- the proximal operator of the l1 norm.

    S       : (H, W, T)      -- current smooth component
    mult_f  : (3, H, W, T)   -- the multiplier lambda_f (NOT the tuning parameter)
    lam     : scalar         -- the tuning parameter lambda, in [0.2, 1]
    beta_f  : positive scalar
    -> f of shape (3, H, W, T), or (f, info) when return_info

    Guards reject the lambda/lambda_f swap at the boundary: passing the
    multiplier as `lam` fails the scalar check, and passing the scalar as
    `mult_f` fails the shape check. Without them the swapped call runs cleanly
    and returns wrong numbers.
    """
    S = np.asarray(S, dtype=np.float64)
    mult_f = np.asarray(mult_f, dtype=np.float64)

    if np.ndim(lam) != 0:
        raise ValueError(
            f"lam must be the SCALAR tuning parameter (got array of shape "
            f"{np.shape(lam)}). The (3, H, W, T) multiplier is `mult_f` -- "
            f"in eq. (11) lambda sets the threshold and lambda_f the shift."
        )
    if np.ndim(beta_f) != 0 or not beta_f > 0:
        raise ValueError(f"beta_f must be a positive scalar (got {beta_f!r}).")
    expected = (3,) + S.shape
    if mult_f.shape != expected:
        raise ValueError(
            f"mult_f must have shape {expected} to match D vec(S) (got "
            f"{mult_f.shape}). If a scalar was passed here, the lambda / "
            f"lambda_f arguments are swapped."
        )

    # A = D vec(S) + lambda_f / beta_f     (the shift uses the MULTIPLIER)
    A = tv_forward(S) + mult_f / beta_f
    tau = lam / beta_f                      # the threshold uses the SCALAR
    f = soft_threshold(A, tau)

    if return_info:
        return f, {"A": A, "tau": float(tau),
                   "zero_fraction": float(np.mean(f == 0.0))}
    return f
