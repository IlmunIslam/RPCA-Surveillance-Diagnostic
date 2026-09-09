"""
Unit tests for Phase 1 component (a): the TV difference operators and Phi.

Covers src/ssrtd_real.py -- tv_forward, tv_adjoint, tv_norm, compute_phi --
against paper/SOURCE.md eq. (4) and (9).

Four tests:
  1. adjoint identity   <D x, y> == <x, D* y>            (required by plan)
  2. Phi vs direct      ifftn(Phi * fftn(x)) == D*D x    (required by plan)
  3. constant -> zero   D(const) == 0 exactly            (catches non-periodic edges)
  4. known small case   hand-checked values + axis mapping

Shapes are deliberately non-cubic so an axis mix-up cannot pass by symmetry.

Run from the project directory as a module:
    python -m src.test_tv_operators
"""

import sys

import numpy as np

from src.ssrtd_real import tv_forward, tv_adjoint, tv_norm, compute_phi

RTOL = 1e-12
SHAPES = [(5, 7, 3), (4, 4, 4), (8, 3, 6), (2, 5, 9)]

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


# ---------------------------------------------------------------- test 1
def test_adjoint_identity():
    """<D x, y> must equal <x, D* y> for random x, y across several shapes."""
    print("\n1. Adjoint identity  <D x, y> == <x, D* y>")
    rng = np.random.default_rng(0)
    ok = True
    for shape in SHAPES:
        x = rng.standard_normal(shape)
        y = rng.standard_normal((3,) + shape)

        lhs = float(np.sum(tv_forward(x) * y))     # <D x, y>
        rhs = float(np.sum(x * tv_adjoint(y)))     # <x, D* y>

        scale = max(abs(lhs), abs(rhs), 1.0)
        rel = abs(lhs - rhs) / scale
        good = rel <= RTOL
        ok &= check(
            f"shape {shape}",
            good,
            f"<Dx,y>={lhs:+.15e}  <x,D*y>={rhs:+.15e}  rel={rel:.2e}",
        )
    return ok


# ---------------------------------------------------------------- test 2
def test_phi_matches_direct():
    """ifftn(Phi * fftn(x)) must equal D*D x, the assumption eq. (9) rests on."""
    print("\n2. Phi vs direct application  ifftn(Phi*fftn(x)) == D*(D x)")
    rng = np.random.default_rng(1)
    ok = True
    for shape in SHAPES:
        x = rng.standard_normal(shape)

        direct = tv_adjoint(tv_forward(x))                        # D*D x
        phi = compute_phi(shape)
        via_fft = np.fft.ifftn(phi * np.fft.fftn(x)).real         # eigenvalue route

        denom = max(float(np.abs(direct).max()), 1.0)
        rel = float(np.abs(direct - via_fft).max()) / denom
        good = rel <= RTOL

        imag = float(np.abs(np.fft.ifftn(phi * np.fft.fftn(x)).imag).max())
        ok &= check(
            f"shape {shape}",
            good and imag <= 1e-12,
            f"max|direct-fft|/scale={rel:.2e}  max|imag|={imag:.2e}  "
            f"Phi in [{phi.min():.3f}, {phi.max():.3f}]",
        )
    return ok


# ---------------------------------------------------------------- test 3
def test_constant_maps_to_zero():
    """D(constant) == 0 exactly. Fails immediately if the edges are not periodic."""
    print("\n3. Constant tensor -> exactly zero (periodic boundary check)")
    ok = True
    for shape in SHAPES:
        for value in (1.0, -3.5):
            S = np.full(shape, value, dtype=np.float64)
            D = tv_forward(S)
            worst = float(np.abs(D).max())
            ok &= check(
                f"shape {shape}, value {value}",
                worst == 0.0,
                f"max|D S| = {worst:.1e} (must be exactly 0), ||S||_TV1 = {tv_norm(S):.1f}",
            )
    return ok


# ---------------------------------------------------------------- test 4
def test_known_small_case():
    """
    Hand-checked values on a ramp, pinning both difference direction and axis
    mapping.

    For S(x,y,t) = x on shape (3,4,5): Dh is +1 stepping up the ramp and -2 at
    the wrap (S[0]-S[2] = 0-2), while Dv and Dt are identically zero. Per
    (y,t) column the absolute sum is 1+1+2 = 4, over 4*5 = 20 columns, so
    ||S||_TV1 = 80.
    """
    print("\n4. Known small case: ramps pin direction and axis mapping")
    shape = (3, 4, 5)
    H, W, T = shape
    idx = np.indices(shape).astype(np.float64)   # idx[k] is the coordinate along axis k
    ok = True

    for axis, name, n in ((0, "Dh (axis 0, height)", H),
                          (1, "Dv (axis 1, width)", W),
                          (2, "Dt (axis 2, time)", T)):
        S = idx[axis]                # ramp along this axis only
        D = tv_forward(S)

        # the matching operator: +1 everywhere except -(n-1) at the wrap slice
        expected = np.ones(shape)
        wrap = [slice(None)] * 3
        wrap[axis] = n - 1
        expected[tuple(wrap)] = -(n - 1)

        this_ok = np.array_equal(D[axis], expected)
        others_zero = all(
            float(np.abs(D[k]).max()) == 0.0 for k in range(3) if k != axis
        )

        # ||S||_TV1 = (per-line abs sum) x (number of lines) = (2(n-1)) x (HWT/n)
        expected_norm = 2.0 * (n - 1) * (H * W * T / n)
        actual_norm = tv_norm(S)
        norm_ok = actual_norm == expected_norm

        ok &= check(
            f"ramp along {name}",
            this_ok and others_zero and norm_ok,
            f"values match={this_ok}  other axes zero={others_zero}  "
            f"||S||_TV1: got {actual_norm:.1f}, expected {expected_norm:.1f}",
        )

    # explicit spot-check of the wrap element, so the direction is unambiguous
    S = idx[0]
    D = tv_forward(S)
    got_step, got_wrap = float(D[0][0, 0, 0]), float(D[0][H - 1, 0, 0])
    ok &= check(
        "forward (not backward) difference at the wrap",
        got_step == 1.0 and got_wrap == -(H - 1),
        f"D[0][0,0,0]={got_step:+.1f} (expect +1.0), "
        f"D[0][{H-1},0,0]={got_wrap:+.1f} (expect {-(H-1):+.1f})",
    )
    return ok


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (a) — TV difference operators + Phi")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (4), (9)")
    print(f"numpy {np.__version__}   rtol {RTOL:g}")
    print("=" * 72)

    tests = [
        test_adjoint_identity,
        test_phi_matches_direct,
        test_constant_maps_to_zero,
        test_known_small_case,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    n_total = len(_results)

    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{n_total} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    if all(outcomes):
        print("Component (a) VERIFIED — all four tests pass.")
        return 0
    print("Component (a) NOT verified — fix before moving to (b).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
