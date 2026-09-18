"""
Unit tests for Phase 1 component (c): the S-update via 3D FFT.

Covers src/ssrtd_real.py -- update_S -- against paper/SOURCE.md eq. (9).

Five tests plus a memory + timing probe:
  1. linear system residual   (beta_X I + beta_f D*D) S == C          (required)
  2. DC bin / constant C      constant C => S == C/beta_X exactly
  3. half vs full spectrum    rfftn/irfftn route == fftn/ifftn route at 1e-12,
                              incl. odd T; wrong-shaped phi is rejected
                              (replaces the old "real output" test, which is
                              vacuous under irfftn -- real by construction)
  4. beta_f = 0 degenerates   S == C/beta_X everywhere
  5. sign / C construction    matches the eq. (8) form of X_tilde

  memory+timing probe         one real VIRAT tensor: peak RSS and s/call.
                              Reported, not pass/fail -- with 8 GB RAM this
                              decides whether (g) needs float32 or rfftn.

Test 2 exists because Phi vanishes at the DC bin (established in component (a):
Phi.min() == 0 on every shape, since D*D annihilates constants). There the eq.
(9) denominator reduces to exactly beta_X, and the true solution has the closed
form C/beta_X. That makes the bin most likely to be wrong the one bin with an
exact answer to check against.

Run from the project directory as a module:
    python -m src.test_s_update
"""

import ctypes
import sys
import time
from ctypes import wintypes

import numpy as np

from src.ssrtd_real import (
    compute_phi, compute_phi_half, half_shape, tv_forward, tv_adjoint,
    tv_adjoint_affine, update_S,
)

RTOL = 1e-12
SHAPES = [(5, 7, 3), (8, 3, 6), (4, 4, 4), (2, 5, 9)]

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def _random_state(shape, rng, beta_X=0.7, beta_f=1.3):
    """A plausible mid-ADMM state: all operands random, penalties positive."""
    return dict(
        X=rng.standard_normal(shape),
        L=rng.standard_normal(shape),
        E=rng.standard_normal(shape),
        mult_X=rng.standard_normal(shape),
        f=rng.standard_normal((3,) + shape),
        mult_f=rng.standard_normal((3,) + shape),
        beta_X=beta_X,
        beta_f=beta_f,
    )


def _rhs(state):
    """C = beta_X (X - L - E) - Lambda_X + ten(D*(beta_f f - lambda_f))."""
    return (state["beta_X"] * (state["X"] - state["L"] - state["E"])
            - state["mult_X"]
            + tv_adjoint(state["beta_f"] * state["f"] - state["mult_f"]))


# ---------------------------------------------------------------- test 1
def test_linear_system_residual():
    """Plug S back into the system it claims to solve: (bX I + bf D*D) S == C."""
    print("\n1. Linear system residual  (beta_X I + beta_f D*D) S == C")
    rng = np.random.default_rng(0)
    ok = True
    for shape in SHAPES:
        st = _random_state(shape, rng)
        phi = compute_phi_half(shape)
        S, info = update_S(**st, phi=phi, return_info=True)

        lhs = st["beta_X"] * S + st["beta_f"] * tv_adjoint(tv_forward(S))
        C = _rhs(st)
        rel = float(np.abs(lhs - C).max() / max(float(np.abs(C).max()), 1.0))

        ok &= check(
            f"shape {shape}",
            rel <= RTOL,
            f"max|(bX I + bf D*D)S - C| / scale = {rel:.3e}   "
            f"(C from update_S matches: "
            f"{float(np.abs(info['C'] - C).max()):.1e})",
        )
    return ok


# ---------------------------------------------------------------- test 2
def test_dc_bin_constant_C():
    """
    Constant C has the exact solution S = C/beta_X, because D*D kills constants.

    This is the DC bin, where Phi == 0 and the denominator is exactly beta_X.
    """
    print("\n2. DC bin: constant C => S == C/beta_X exactly")
    rng = np.random.default_rng(1)
    ok = True
    for shape in SHAPES:
        beta_X, beta_f = 0.37, 4.2
        const = float(rng.standard_normal())

        # drive C to a constant: no TV contribution, X - L - E constant,
        # Lambda_X zero
        zero3 = np.zeros((3,) + shape)
        st = dict(
            X=np.full(shape, const / beta_X), L=np.zeros(shape), E=np.zeros(shape),
            mult_X=np.zeros(shape), f=zero3, mult_f=zero3,
            beta_X=beta_X, beta_f=beta_f,
        )
        phi = compute_phi_half(shape)
        S, info = update_S(**st, phi=phi, return_info=True)

        expected = np.full(shape, const / beta_X)
        rel = float(np.abs(S - expected).max() / max(abs(const / beta_X), 1.0))

        dc_ok = abs(info["denom_min"] - beta_X) < 1e-15
        phi_dc = float(phi.min())

        ok &= check(
            f"shape {shape}",
            rel <= 1e-14 and dc_ok,
            f"max|S - C/beta_X| / scale = {rel:.3e}; "
            f"Phi.min() = {phi_dc:.1e}, denom.min() = {info['denom_min']:.6f} "
            f"(== beta_X {beta_X}: {dc_ok})",
        )

    # the guard itself must fire when beta_X = 0
    st = _random_state((4, 5, 6), rng, beta_X=0.0, beta_f=1.0)
    try:
        update_S(**st)
        fired = False
    except ValueError:
        fired = True
    ok &= check(
        "beta_X = 0 raises rather than emitting inf/nan",
        fired,
        "denominator would be beta_f * Phi, which is exactly 0 at the DC bin",
    )
    return ok


# ---------------------------------------------------------------- test 3
def test_half_vs_full_spectrum():
    """
    A/B: the rfftn/irfftn route must equal the original fftn/ifftn route.

    rfftn is mathematically exact for real input (the spectrum is conjugate
    symmetric, so the half grid carries everything), so agreement must be at
    machine-epsilon scale. This is the property the old "real output" test can
    no longer guard: irfftn returns real by construction, so max_imag is 0 by
    definition on the new route. Shapes include odd T, where irfftn without
    s= would silently return the wrong length.
    """
    print("\n3. Half-spectrum (rfftn) route == full-spectrum (fftn) route")
    rng = np.random.default_rng(2)
    ok = True
    for shape in SHAPES + [(6, 8, 11), (7, 9, 12)]:
        st = _random_state(shape, rng)
        S_full = update_S(**st, phi=compute_phi(shape), half_spectrum=False)
        S_half, info = update_S(**st, phi=compute_phi_half(shape),
                                half_spectrum=True, return_info=True)

        scale = max(float(np.abs(S_full).max()), 1.0)
        rel = float(np.abs(S_half - S_full).max()) / scale
        ok &= check(
            f"shape {shape}{' (odd T)' if shape[2] % 2 else ''}",
            rel <= RTOL and S_half.shape == shape and np.isrealobj(S_half)
            and info["half_spectrum"] is True,
            f"max|S_half - S_full| / scale = {rel:.3e}; shape {S_half.shape} "
            f"(input {shape}); dtype {S_half.dtype}",
        )

    # the default route is the half-spectrum one, and it is what ssrtd_real uses
    st = _random_state((5, 7, 3), rng)
    _, info = update_S(**st, return_info=True)
    ok &= check("default route is half-spectrum", info["half_spectrum"] is True,
                "ssrtd_real hoists compute_phi_half and relies on this default")

    # passing the wrong phi shape for the route must fail loudly, not broadcast
    for phi, half, label in ((compute_phi((5, 7, 3)), True, "full phi to half route"),
                             (compute_phi_half((5, 7, 3)), False, "half phi to full route")):
        try:
            update_S(**st, phi=phi, half_spectrum=half)
            fired = False
        except ValueError:
            fired = True
        ok &= check(f"{label} raises", fired,
                    f"phi {phi.shape}, half_spectrum={half}")
    return ok


# ---------------------------------------------------------------- test 4
def test_beta_f_zero():
    """beta_f = 0 removes the TV coupling: S must be exactly C/beta_X."""
    print("\n4. beta_f = 0 degenerates to S == C/beta_X")
    rng = np.random.default_rng(3)
    ok = True
    for shape in SHAPES:
        st = _random_state(shape, rng, beta_X=1.7, beta_f=0.0)
        S, info = update_S(**st, return_info=True)

        expected = _rhs(st) / st["beta_X"]
        rel = float(np.abs(S - expected).max() / max(float(np.abs(expected).max()), 1.0))
        flat = abs(info["denom_max"] - info["denom_min"]) < 1e-15

        ok &= check(
            f"shape {shape}",
            rel <= 1e-13 and flat,
            f"max|S - C/beta_X| / scale = {rel:.3e}; denominator flat at "
            f"{info['denom_min']:.4f} across all bins = {flat}",
        )
    return ok


# ---------------------------------------------------------------- test 5
def test_sign_convention():
    """
    The C used internally must equal the eq. (8) form.

    eq. (8) has X_tilde = X - S - E - Lambda_X/beta_X, so the eq. (9) right-hand
    side must factor as beta_X * (X - L - E - Lambda_X/beta_X) + D*(...). A sign
    slip on Lambda_X or lambda_f converges to something plausible rather than
    failing loudly, so it is checked explicitly.
    """
    print("\n5. Sign convention: C matches the eq. (8) form")
    rng = np.random.default_rng(4)
    ok = True
    for shape in SHAPES:
        st = _random_state(shape, rng)
        _, info = update_S(**st, return_info=True)

        eq8_form = (st["beta_X"] * (st["X"] - st["L"] - st["E"]
                                    - st["mult_X"] / st["beta_X"])
                    + tv_adjoint(st["beta_f"] * st["f"] - st["mult_f"]))
        rel = float(np.abs(info["C"] - eq8_form).max()
                    / max(float(np.abs(eq8_form).max()), 1.0))

        # and a wrong sign on Lambda_X must NOT match, or the test is vacuous
        wrong = (st["beta_X"] * (st["X"] - st["L"] - st["E"]) + st["mult_X"]
                 + tv_adjoint(st["beta_f"] * st["f"] - st["mult_f"]))
        differs = float(np.abs(info["C"] - wrong).max()) > 1e-8

        ok &= check(
            f"shape {shape}",
            rel <= 1e-14 and differs,
            f"max|C - eq8_form| / scale = {rel:.3e}; "
            f"sign-flipped Lambda_X is distinguishable = {differs}",
        )
    return ok


# ---------------------------------------------------------------- test 6
def test_adjoint_affine():
    """
    Memory lever C: tv_adjoint_affine(a, F, M) must equal tv_adjoint(a*F - M).
    It sums the same three per-component terms in the same order, so the bits
    are expected to match; the assertion allows 1e-13 relative in case a BLAS
    or roll path reassociates. update_S's C must be unchanged as a result.
    """
    print("\n6. tv_adjoint_affine == tv_adjoint(a*F - M) (memory lever C)")
    rng = np.random.default_rng(6)
    ok = True
    for shape in SHAPES + [(6, 8, 11)]:
        F = rng.standard_normal((3,) + shape)
        M = rng.standard_normal((3,) + shape)
        for a in (0.0, 1.0, 1.3, 7815.27):
            ref = tv_adjoint(a * F - M)
            got = tv_adjoint_affine(a, F, M)
            rel = float(np.abs(got - ref).max()) / max(float(np.abs(ref).max()), 1.0)
            ok &= check(
                f"shape {shape}, a={a}",
                rel <= 1e-13 and got.shape == shape,
                f"rel diff {rel:.1e}; bitwise={got.tobytes() == ref.tobytes()}",
            )

    # update_S end to end: C (and hence S) unchanged against the direct formula
    for shape in SHAPES[:2]:
        st = _random_state(shape, rng)
        _, info = update_S(**st, return_info=True)
        C_direct = _rhs(st)
        rel = float(np.abs(info["C"] - C_direct).max()) / max(float(np.abs(C_direct).max()), 1.0)
        ok &= check(f"update_S C via affine adjoint == direct formula, shape {shape}",
                    rel <= 1e-13, f"rel diff {rel:.1e}; bitwise={info['C'].tobytes() == C_direct.tobytes()}")
    return ok


# ---------------------------------------------------------------- probe
class _MEMCOUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def _mem_mb():
    """
    (current, peak) working set in MB. Windows only; psutil is not installed.

    argtypes/restype must be declared. Without them ctypes treats the
    GetCurrentProcess() pseudo-handle ((HANDLE)-1) as a 32-bit int, the handle
    reaches the API truncated, the call fails, and the struct is left zeroed --
    which reads as a plausible-looking 0 MB rather than an error.
    """
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_MEMCOUNTERS), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    c = _MEMCOUNTERS()
    c.cb = ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError("GetProcessMemoryInfo failed "
                      f"(error {ctypes.get_last_error()})")
    return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20


def memory_timing_probe():
    """Full-size VIRAT tensor: peak RSS and seconds per update_S call."""
    print("\n" + "-" * 72)
    print("MEMORY + TIMING PROBE — one real VIRAT tensor, float64")
    print("-" * 72)
    try:
        shape = (180, 320, 300)
        nbytes = int(np.prod(shape)) * 8 / 2**20

        base_cur, base_peak = _mem_mb()
        print(f"  shape {shape}  ({int(np.prod(shape)):,} elements, "
              f"{nbytes:.0f} MB per float64 tensor)")
        print(f"  baseline working set : {base_cur:8.0f} MB  "
              f"(peak so far {base_peak:.0f} MB)")

        rng = np.random.default_rng(0)
        st = dict(
            X=rng.standard_normal(shape), L=rng.standard_normal(shape),
            E=rng.standard_normal(shape), mult_X=rng.standard_normal(shape),
            f=rng.standard_normal((3,) + shape),
            mult_f=rng.standard_normal((3,) + shape),
            beta_X=0.7, beta_f=1.3,
        )
        after_alloc, _ = _mem_mb()
        print(f"  after allocating state: {after_alloc:8.0f} MB   "
              f"(X,L,E,Lambda_X + f,lambda_f = 4x{nbytes:.0f} + 2x{3*nbytes:.0f} MB)")

        t0 = time.perf_counter()
        phi = compute_phi_half(shape)
        t_phi = time.perf_counter() - t0
        print(f"  compute_phi_half     : {t_phi:8.2f} s  (once; shape {phi.shape}, "
              f"{phi.nbytes/2**20:.0f} MB vs {2*phi.nbytes/2**20:.0f} MB full)")

        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            S = update_S(**st, phi=phi)
            times.append(time.perf_counter() - t0)
        cur, peak = _mem_mb()

        print(f"  update_S             : {np.mean(times):8.2f} s/call "
              f"(min {min(times):.2f}, max {max(times):.2f} over 3 calls)")
        print(f"  working set now      : {cur:8.0f} MB")
        print(f"  PEAK working set     : {peak:8.0f} MB   "
              f"<-- headroom against 8 GB: {8192 - peak:.0f} MB")
        print(f"  S stats              : dtype {S.dtype}, "
              f"range [{S.min():.3f}, {S.max():.3f}]")
        print()
        print("  This probe measures update_S alone on top of a 1,390 MB state.")
        print("  Before the rfftn change it peaked at 2,840 MB (6.33 s/call).")
        print("  The full-ADMM peak was measured on VIRAT video_01 on 2026-09-19:")
        print("  3,512 MB, 35.9 min -- see RESEARCH_LOG.md section 7.")
        return True
    except Exception as exc:                     # probe must never fail the suite
        print(f"  probe skipped: {type(exc).__name__}: {exc}")
        return True


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (c) — S-update via 3D FFT")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (9)")
    print(f"numpy {np.__version__}   rtol {RTOL:g}")
    print("=" * 72)

    tests = [
        test_linear_system_residual,
        test_dc_bin_constant_C,
        test_half_vs_full_spectrum,
        test_beta_f_zero,
        test_sign_convention,
        test_adjoint_affine,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{len(_results)} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    memory_timing_probe()

    print()
    if all(outcomes):
        print("Component (c) VERIFIED — all six tests pass.")
        return 0
    print("Component (c) NOT verified — fix before moving to (d).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
