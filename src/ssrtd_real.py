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
    (e) E-update (sparse noise)                    -- this file, below
    (f) Multiplier + adaptive penalty updates      -- this file, below
    (g) Full ADMM assembly (Algorithm 1)           -- this file, below
"""

import time

import numpy as np

# Reuse the repo's existing helpers rather than adding another copy;
# tensor_rpca.py and ssrtd.py already define these. soft_threshold there is
# character-for-character the paper's definition,
# soft(A, tau) = sign(A) * max(|A| - tau, 0), used by both (d) and (e).
from src.tensor_rpca import unfold, fold, soft_threshold, soft_threshold_inplace

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


def tv_adjoint_affine(a, F, M):
    """
    tv_adjoint(a * F - M) without ever forming the stacked (3, H, W, T)
    combination (memory lever C, used by the eq. (9) S-update).

    Accumulates one component at a time with (H, W, T) buffers: for each k,
    buf = a * F[k] - M[k], then acc += roll(buf, +1, axis_k) - buf. That is the
    same per-component term tv_adjoint sums, in the same k order, so the result
    agrees with tv_adjoint(a * F - M) to round-off (test_s_update test 6 asserts
    1e-13 relative; the two sum three terms in the same order, so in practice
    the bits match).

    a : scalar; F, M : (3, H, W, T)  ->  (H, W, T)
    """
    F = np.asarray(F)
    M = np.asarray(M)
    acc = None
    for i, ax in enumerate(_AXES):
        buf = a * F[i]
        buf -= M[i]
        term = np.roll(buf, +1, axis=ax)
        term -= buf
        acc = term if acc is None else acc + term
    return acc


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


def half_shape(shape):
    """Shape of rfftn output for a real (H, W, T) input: the LAST axis (time)
    is reduced to T//2 + 1. numpy's rfftn always halves the last axis."""
    return tuple(shape[:-1]) + (shape[-1] // 2 + 1,)


def compute_phi_half(shape):
    """
    Phi on the half spectrum, for the rfftn/irfftn form of the eq. (9) solve.

    Same construction as compute_phi -- the eigenvalues of each circulant D_k
    from the rfftn of its impulse response, |.|^2, summed -- so it stays
    consistent with tv_forward by construction. Built directly on the half
    grid, NOT by computing full Phi and slicing, which would allocate the full
    array and defeat the purpose.

    Analytically, for periodic forward differences
        Phi[k1,k2,k3] = 4 [ sin^2(pi k1/H) + sin^2(pi k2/W) + sin^2(pi k3/T) ],
    verified to 1.8e-15 against compute_phi on 2026-09-18 (test_tv_operators
    test 5 checks this closed form as an oracle independent of this code).

    The DC bin is still present on the half grid (Phi_half.min() == 0), so the
    beta_X * 1 term in the eq. (9) denominator is still what keeps it invertible.

    shape : (H, W, T)
    -> (H, W, T//2 + 1) real non-negative array
    """
    delta = np.zeros(shape, dtype=np.float64)
    delta[0, 0, 0] = 1.0
    D_delta = tv_forward(delta)
    return sum(np.abs(np.fft.rfftn(D_delta[i])) ** 2 for i in range(3))


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


def hooi(X, ranks=None, n_iter=20, return_history=False, init_Us=None):
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

    # init_Us warm-starts from a previous solve. Algorithm 1 does not do this --
    # it is a deviation, off by default, and only enabled via ssrtd_real's
    # warm_start flag after being measured. See IMPLEMENTATION_PLAN.md (g).
    if init_Us is not None and all(
            init_Us[k].shape == (X.shape[k], ranks[k]) for k in range(3)):
        Us = [U.copy() for U in init_Us]
    else:
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
             return_info=False, half_spectrum=True):
    """
    Closed-form S-update, eq. (9).

    X, L, E, mult_X : (H, W, T)      -- data, low-rank, sparse, and Lambda_X
    f, mult_f       : (3, H, W, T)   -- TV auxiliary and its multiplier lambda_f
    beta_X, beta_f  : positive scalars
    phi             : precomputed Phi; computed here if omitted, but the paper
                      notes it "only needs to be calculated once in the whole
                      algorithm", so hoist it out of the ADMM loop. Must be
                      compute_phi_half(shape) when half_spectrum is True and
                      compute_phi(shape) when it is False -- the shape is checked.
    half_spectrum   : True (default) solves with rfftn/irfftn. C is real, so its
                      spectrum is conjugate-symmetric and the half grid carries
                      everything; the two routes are mathematically identical
                      (test_s_update test 3 asserts agreement at 1e-12). The
                      half route holds ~half the complex temporaries. False keeps
                      the original fftn/ifftn path, retained so the A/B test
                      compares against the real previous implementation.
    -> S, or (S, info) when return_info

    The half route MUST pass s=shape (and axes=) to irfftn: rfftn maps T=10 and
    T=11 to the same 6 bins, and irfftn without s= reconstructs the wrong
    length silently. Nothing here computes a norm or energy in the Fourier
    domain -- the solve is a pointwise division -- so no DC/Nyquist
    double-counting correction is needed.

    Sign convention cross-checks against eq. (8): beta_X(X - L - E) - Lambda_X
    equals beta_X * (X - L - E - Lambda_X/beta_X), and X_tilde in eq. (8) is
    X - S - E - Lambda_X/beta_X. Same convention, so a sign slip here would
    contradict (8) rather than merely look wrong.
    """
    X = np.asarray(X, dtype=np.float64)
    shape = X.shape
    if phi is None:
        phi = compute_phi_half(shape) if half_spectrum else compute_phi(shape)
    expected = half_shape(shape) if half_spectrum else shape
    if phi.shape != expected:
        raise ValueError(
            f"phi has shape {phi.shape} but the {'half' if half_spectrum else 'full'}"
            f"-spectrum route needs {expected}. Use "
            f"{'compute_phi_half' if half_spectrum else 'compute_phi'}(shape), "
            f"or set half_spectrum to match the phi you have."
        )

    # tv_adjoint(beta_f * f - mult_f) without the two (3,H,W,T) temporaries
    # (lever C); same per-component sums in the same order.
    C = beta_X * (X - L - E) - mult_X + tv_adjoint_affine(beta_f, f, mult_f)

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

    if half_spectrum:
        Y = np.fft.rfftn(C)                       # (H, W, T//2+1), complex
        np.divide(Y, denom, out=Y)                # in place: no second complex array
        S = np.fft.irfftn(Y, s=shape, axes=(0, 1, 2))   # real by construction
        max_imag = 0.0                            # nothing is discarded on this route
    else:
        S_complex = np.fft.ifftn(np.fft.fftn(C) / denom)
        S = S_complex.real
        max_imag = float(np.abs(S_complex.imag).max())

    if return_info:
        scale = max(float(np.abs(S).max()), 1.0)
        return S, {
            "denom_min": denom_min,
            "denom_max": float(denom.max()),
            "max_imag": max_imag,
            "max_imag_rel": max_imag / scale,
            "half_spectrum": half_spectrum,
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


def update_f(S, mult_f, lam, beta_f, return_info=False, DS=None):
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
    # DS may be passed in when the caller already holds tv_forward(S) -- the
    # ADMM loop computes it once per iteration and shares it (memory lever B).
    # Built as (mult_f / beta_f) += DS: addition commutes, so the bits equal
    # DS + mult_f / beta_f, with one fewer (3,H,W,T) temporary at the peak stage.
    if DS is None:
        DS = tv_forward(S)
    A = mult_f / beta_f
    A += DS
    tau = lam / beta_f                      # the threshold uses the SCALAR
    A_copy = A.copy() if return_info else None   # info["A"]; tests only
    # In place: A is a fresh (3,H,W,T) array we own, and this stage is the
    # memory peak of the whole ADMM loop. soft_threshold would allocate four
    # temporaries of A's size here; the in-place form allocates one. Bitwise
    # identical (test_f_update test 6).
    f = soft_threshold_inplace(A, tau)

    if return_info:
        return f, {"A": A_copy, "tau": float(tau),
                   "zero_fraction": float(np.mean(f == 0.0))}
    return f


# ===========================================================================
# (e) E-update, sparse noise -- eq. (12)
# ===========================================================================
#
#   E = soft( X - L - S - Lambda_X/beta_X ,  2/beta_X )                  (12)
#
# THE THRESHOLD CONSTANT IS DISPUTED, AND WE IMPLEMENT WHAT IS PRINTED.
#
# eq. (12) prints 2/beta_X. We verified that against a rendered page image
# because it looked unusual, and it is definitely a 2. But the paper's own
# Appendix A derivation does not support it:
#
#   eq. (17) reduces the E-terms of the augmented Lagrangian to
#       (beta_X/2) ||X - L - S - Lambda_X/beta_X - E||_F^2 + ||E||_1 + const
#   i.e. min_E ||E||_1 + (beta_X/2)||A - E||^2  with A = X - L - S - Lambda_X/beta_X.
#
# That is the same form as eq. (16), which the paper carries into (10) and
# solves in (11) with threshold lambda/beta_f. Applying the identical pattern
# here, where the ||E||_1 coefficient is 1, gives 1/beta_X, not 2/beta_X.
# Appendix A prints "Thus, the equation (12) can be derived" and shows no
# shrinkage step, so nothing in the paper justifies the 2. The (beta/2)
# convention IS present in (15), (16) and (17), so the factor is not explained
# by an unconventional Lagrangian scaling either.
#
# Most likely a typo -- but calling it one in code would substitute our
# expectation for the source, which is the failure mode this project exists to
# correct. So: implement 2.0 as printed, expose `factor` so 1.0 is a one-line
# experiment, and resolve it by measurement on real data at assembly (g).
# See PAPER_NOTES.md item 11.

E_THRESHOLD_FACTOR = 2.0


def update_E(X, L, S, mult_X, beta_X, factor=E_THRESHOLD_FACTOR,
             return_info=False):
    """
    Closed-form E-update, eq. (12).

    X, L, S, mult_X : (H, W, T)
    beta_X          : positive scalar
    factor          : threshold numerator. Defaults to 2.0, exactly as eq. (12)
                      prints. Pass 1.0 for the value Appendix A's eq. (17)
                      implies; see the note above.
    -> E, or (E, info) when return_info

    The argument is  A = X - L - S - Lambda_X/beta_X. Note this is NOT either of
    the two neighbouring residuals, which differ by one term each:
        eq. (8):  X_tilde = X - S - E - Lambda_X/beta_X   (drops L, carries E)
        eq. (9):  X - L - E                               (drops S, no multiplier)
    All three are plausible-looking and produce output; test_e_update.py pins
    which one this is.
    """
    X = np.asarray(X, dtype=np.float64)
    if np.ndim(beta_X) != 0 or not beta_X > 0:
        raise ValueError(f"beta_X must be a positive scalar (got {beta_X!r}).")

    A = X - L - S - mult_X / beta_X
    tau = factor / beta_X
    E = soft_threshold(A, tau)

    if return_info:
        return E, {"A": A, "tau": float(tau), "factor": float(factor),
                   "zero_fraction": float(np.mean(E == 0.0))}
    return E


# ===========================================================================
# (f) Multiplier and adaptive penalty updates -- eq. (13), (14)
# ===========================================================================
#
# eq. (13):  lambda_f <- lambda_f - gamma * beta_f * (f - D vec(S))
#            Lambda_X <- Lambda_X - gamma * beta_X * (X - L - S - E)
#
# eq. (14), printed for beta_f only:
#            beta_f <- c1 * beta_f   if Err(f^{k+1}) >= c2 * Err(f^k)
#                      beta_f        otherwise
#            Err(f^k) = ||f_k - D vec(S_k)||
#
# with gamma = 1.1, c1 = 1.15, c2 = 0.95.
#
# THE MINUS SIGN IS CORRECT, BECAUSE OF eq. (7). Textbook ADMM usually writes
# lambda <- lambda + rho * c. The paper writes minus, and that follows from its
# augmented Lagrangian (7) being defined with a NEGATIVE inner product,
# -<lambda_f, f - Dvec(S)>. Dual ascent then moves along -c, not +c. The sign
# here is tied to (7), not to convention; test_multipliers.py verifies that link
# numerically rather than assuming it.
#
# THE GROWTH CONDITION IS EASY TO INVERT. beta grows only when the residual
# FAILS to shrink -- Err_new >= c2 * Err_old means "still at least 95% of the
# previous error, so we are not making progress; tighten the penalty". The
# comparison is >=, so exact equality grows. beta never decreases, and eq. (14)
# imposes NO CAP (unlike the old baseline's min(mu * 1.5, 1e6) in ssrtd.py).

GAMMA = 1.1    # multiplier step scale, eq. (13)
C1 = 1.15      # penalty growth factor, eq. (14)
C2 = 0.95      # progress threshold, eq. (14)


def primal_residuals(f, S, X, L, E, DS=None):
    """
    The two constraint residuals of eq. (6), as norms.

    err_f = ||f - D vec(S)||        -- the paper's Err(f^k), eq. (14)
    err_X = ||X - L - S - E||_F     -- INFERRED, see below

    NOTE: eq. (14) is printed for beta_f only, prefaced "Take beta_f as an
    example", and the paper never states the error measure for beta_X. We use
    the natural counterpart: the primal residual of the other constraint of
    eq. (6). This is an inference, not something the paper specifies. Disclosed
    in PAPER_NOTES.md.
    """
    if DS is None:                      # lever B: the loop passes tv_forward(S)
        DS = tv_forward(S)
    err_f = float(np.linalg.norm(np.asarray(f - DS).ravel()))
    err_X = float(np.linalg.norm(np.asarray(X - L - S - E).ravel()))
    return err_f, err_X


def update_multipliers(mult_f, mult_X, f, S, X, L, E, beta_f, beta_X,
                       gamma=GAMMA, DS=None):
    """
    Multiplier updates, eq. (13). Returns new (mult_f, mult_X); inputs unchanged.

    gamma scales the MULTIPLIER step and is 1.1. It is not c1 (1.15), which
    scales the penalty in eq. (14). The two are within 0.05 of each other and
    both multiply something -- keep them straight.
    """
    if DS is None:                      # lever B: the loop passes tv_forward(S)
        DS = tv_forward(S)
    # Same operations in the same order as  mult_f - gamma*beta_f*(f - DS):
    # the scalar gamma*beta_f is formed first either way, then applied to the
    # residual, then subtracted -- so the bits are identical, with one
    # (3,H,W,T) temporary instead of three.
    r = f - DS
    r *= gamma * beta_f
    new_mult_f = mult_f - r
    new_mult_X = mult_X - gamma * beta_X * (X - L - S - E)
    return new_mult_f, new_mult_X


def update_penalty(beta, err_new, err_prev, c1=C1, c2=C2):
    """
    Adaptive penalty update, eq. (14). Returns (beta, grew).

    beta grows by c1 ONLY IF err_new >= c2 * err_prev, i.e. only when the
    residual failed to shrink by the factor c2. Otherwise beta is unchanged.
    beta never decreases, and there is no upper cap.

    On the first iteration there is no previous error. Pass err_prev = inf: the
    condition is then False and beta is left alone, which is the sane default.
    (g) owns that bookkeeping -- this function stays stateless so it can be
    tested exhaustively.
    """
    grew = bool(err_new >= c2 * err_prev)
    return (c1 * beta if grew else beta), grew


# ===========================================================================
# (g) Full ADMM assembly -- Algorithm 1
# ===========================================================================
#
#   Input: X; parameter lambda.
#   Init:  r1,r2,r3 as above; L from (r1,r2,r3)-Tucker of X; S = X - L;
#          beta_f = 1e+1/mean(X), beta_X = 4e-1/mean(X);
#          all other variables 0.
#   Loop:  L via (8); S via (9); f via (11); E via (12); multipliers and
#          penalties via (13), (14).
#   Stop:  ||E_t - E_{t-1}||_F / max{1, ||E_{t-1}||_F} <= 1e-6, or iter > 100.
#
# TWO AMBIGUITIES IN ALGORITHM 1, RESOLVED EXPLICITLY.
#
# 1. `f` is initialized to ZERO, not to D vec(S). The paper says "Other
#    variables are initialized by 0", and f is one of them. Seeding
#    f = D vec(S) is the helpful-looking thing to do and is NOT what is
#    written; it would also make the first f-residual identically zero.
#
# 2. The stopping test compares E_t with E_{t-1}, neither of which exists
#    before the first iteration. Taken literally with E initialized to 0, the
#    relative change would be 0 and the loop would never execute. We force the
#    first iteration (relative change starts at infinity), which is the only
#    reading under which the algorithm runs at all.
#
# 3. THE STOPPING RULE TERMINATES AFTER ONE ITERATION IF TAKEN LITERALLY.
#    E is initialized to 0, and the first E-update also returns exactly 0,
#    because the threshold 2/beta_X = 2*mean(X)/4e-1 = 5*mean(X) is far larger
#    than the initial residual |X - L - S|. The stopping measure is then
#    ||E_1 - E_0||_F / max{1, ||E_0||_F} = 0 / 1 = 0 <= 1e-6, so Algorithm 1
#    halts after a single iteration having accomplished nothing.
#
#    This is scale-invariant -- beta_X is defined as 4e-1/mean(X), so the
#    threshold scales with the data and the degeneracy survives any
#    normalization. It is not an artifact of our [0,1] frames.
#
#    The algorithm is fine; the criterion is. beta_X grows under eq. (14), the
#    threshold shrinks, and E becomes nonzero after a few iterations, after
#    which the measure is meaningful. So: the relative change of an identically
#    zero sequence carries no information, and we do not treat it as
#    convergence. The test is skipped while ||E_{t-1}||_F == 0. If E never
#    becomes nonzero the loop simply runs to max_iter and reports
#    converged=False, which is the honest outcome.
#
#    Recorded in PAPER_NOTES.md; it is a reproducible defect in the published
#    algorithm that any faithful reimplementation hits immediately.


def ssrtd_real(X, lam, max_iter=100, tol=1e-6, factor=E_THRESHOLD_FACTOR,
               hooi_iters=20, warm_start=False, log=True, verbose=False,
               L_true=None):
    """
    Smooth Sparse Robust Tensor Decomposition -- Shen et al. 2022, Algorithm 1.

    X          : (H, W, T) array, the noisy video
    lam        : the single tuning parameter lambda; the paper recommends [0.2, 1]
    max_iter   : outer iterations (paper: 100)
    tol        : relative-change stopping threshold on E (paper: 1e-6)
    factor     : E-threshold numerator. 2.0 as eq. (12) prints; 1.0 is what
                 Appendix A's eq. (17) implies. See PAPER_NOTES.md item 11.
    hooi_iters : inner HOOI iterations (paper: 20)
    warm_start : reuse the previous iteration's Tucker factors. NOT in
                 Algorithm 1 -- a deviation, off by default.
    L_true     : optional ground-truth background, enabling relErr_L in the log
                 (used by the verification gate to reproduce the paper's Fig. 3)

    -> dict with L, S, E, G, Us, f, mult_f, mult_X, beta_f, beta_X, ranks,
       n_iter, converged, history
    """
    X = np.asarray(X, dtype=np.float64)
    if np.ndim(lam) != 0:
        raise ValueError(f"lam must be a scalar (got shape {np.shape(lam)}).")
    shape = X.shape

    mean_X = float(np.mean(X))
    if mean_X == 0:
        raise ValueError("mean(X) is zero; the paper's beta initialization "
                         "1e+1/mean(X), 4e-1/mean(X) is undefined.")

    # --- initialization, exactly as Algorithm 1 prints it -------------------
    ranks = tucker_ranks(shape)
    G, Us, L = hooi(X, ranks, n_iter=hooi_iters)        # Tucker of X, not X_tilde
    S = X - L
    E = np.zeros(shape)                                 # "other variables ... 0"
    mult_X = np.zeros(shape)
    f = np.zeros((3,) + shape)                          # zero, NOT D vec(S)
    mult_f = np.zeros((3,) + shape)
    beta_f = 1e+1 / mean_X
    beta_X = 4e-1 / mean_X

    phi = compute_phi_half(shape)   # depends only on shape -- computed once; half
                                    # spectrum, matching update_S's default route
    ranks_eff = feasible_ranks(shape, ranks)

    err_f_prev = err_X_prev = np.inf
    rel_chg = np.inf                # forces the first iteration; see note above
    history = []
    n_iter = 0
    converged = False

    while rel_chg > tol and n_iter < max_iter:
        t0 = time.perf_counter()
        L_prev, S_prev, E_prev = L, S, E

        # line 2: L via (8), on X_tilde = X - S - E - Lambda_X/beta_X
        X_tilde = X - S - E - mult_X / beta_X
        G, Us, L = hooi(X_tilde, ranks, n_iter=hooi_iters,
                        init_Us=Us if warm_start else None)
        del X_tilde
        # lever D: take relChg_L now and release the previous L, instead of
        # holding it through the f-update (the memory peak). Same number the
        # log row used to compute at the end of the iteration.
        relchg_L = _rel_change(L, L_prev)
        del L_prev

        # line 3: S via (9)
        S = update_S(X, L, E, mult_X, f, mult_f, beta_X, beta_f, phi=phi)
        relchg_S = _rel_change(S, S_prev)       # lever D, as above
        del S_prev

        # line 4: f via (11), anisotropic TV
        DS = tv_forward(S)              # lever B: once per iteration, shared by
        f = update_f(S, mult_f, lam, beta_f, DS=DS)   # f, residuals, multipliers, log

        # line 5: E via (12)
        E = update_E(X, L, S, mult_X, beta_X, factor=factor)

        # line 6: multipliers via (13), then penalties via (14)
        err_f, err_X = primal_residuals(f, S, X, L, E, DS=DS)
        mult_f, mult_X = update_multipliers(mult_f, mult_X, f, S, X, L, E,
                                            beta_f, beta_X, DS=DS)
        beta_f, grew_f = update_penalty(beta_f, err_f, err_f_prev)
        beta_X, grew_X = update_penalty(beta_X, err_X, err_X_prev)
        err_f_prev, err_X_prev = err_f, err_X
        n_iter += 1

        rel_chg = _rel_change(E, E_prev)
        # Ambiguity 3: while E has never been nonzero, the relative change is
        # identically 0 and carries no information. Do not call that convergence.
        e_prev_norm = float(np.linalg.norm(E_prev.ravel()))
        if rel_chg <= tol and e_prev_norm > 0.0:
            converged = True
        elif rel_chg <= tol:
            rel_chg = np.inf        # keep iterating; E is still identically zero

        if log:
            row = {
                "iter": n_iter,
                "relChg_L": relchg_L,           # computed right after the L update
                "relChg_S": relchg_S,           # computed right after the S update
                "relChg_E": rel_chg,
                "relErr_L": (_rel_error(L, L_true) if L_true is not None
                             else float("nan")),
                "err_f": err_f,
                "err_X": err_X,
                "beta_f": beta_f,
                "beta_X": beta_X,
                "beta_f_grew": grew_f,
                "beta_X_grew": grew_X,
                "obj_E_l1": float(np.abs(E).sum()),
                # == lam * tv_norm(S), which is lam * |tv_forward(S)|.sum();
                # uses the shared DS instead of a fourth tv_forward(S)
                "obj_S_tv1": float(lam * np.abs(DS).sum()),
                "seconds": time.perf_counter() - t0,
            }
            history.append(row)
            if verbose:
                print(f"  iter {row['iter']:3d}  relChg_E {row['relChg_E']:.3e}  "
                      f"err_X {row['err_X']:.4f}  beta_X {row['beta_X']:.4f}"
                      f"{' +' if grew_X else '  '}  {row['seconds']:.2f}s")
        del DS                          # (3,H,W,T): release before the next L/S update

    return {"L": L, "S": S, "E": E, "G": G, "Us": Us, "f": f,
            "mult_f": mult_f, "mult_X": mult_X,
            "beta_f": beta_f, "beta_X": beta_X,
            "ranks": ranks, "ranks_effective": ranks_eff,
            "lam": float(lam), "factor": float(factor),
            "n_iter": n_iter, "converged": converged, "history": history}


def _rel_change(A, A_prev):
    """||A - A_prev||_F / max{1, ||A_prev||_F} -- Algorithm 1's stopping measure."""
    return float(np.linalg.norm((A - A_prev).ravel())
                 / max(1.0, float(np.linalg.norm(np.asarray(A_prev).ravel()))))


def _rel_error(A, A_true):
    """||A - A_true||_F / max{1, ||A_true||_F} -- the paper's relErr, section IV-A."""
    return float(np.linalg.norm((A - A_true).ravel())
                 / max(1.0, float(np.linalg.norm(np.asarray(A_true).ravel()))))
