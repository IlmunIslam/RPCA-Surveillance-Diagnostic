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
    (b) Tucker / HOOI low-rank solver for L        -- not yet built
    (c) S-update via 3D FFT                        -- not yet built
    (d) f-update (TV auxiliary)                    -- not yet built
    (e) E-update (sparse noise)                    -- not yet built
    (f) Multiplier + adaptive penalty updates      -- not yet built
    (g) Full ADMM assembly (Algorithm 1)           -- not yet built
"""

import numpy as np

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
