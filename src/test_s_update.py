"""
Unit tests for Phase 1 component (c): the S-update via 3D FFT.

Covers src/ssrtd_real.py -- update_S -- against paper/SOURCE.md eq. (9).

Five tests plus a memory + timing probe:
  1. linear system residual   (beta_X I + beta_f D*D) S == C          (required)
  2. DC bin / constant C      constant C => S == C/beta_X exactly
  3. real output              discarded imaginary part is negligible
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

from src.ssrtd_real import compute_phi, tv_forward, tv_adjoint, update_S

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
        phi = compute_phi(shape)
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
        phi = compute_phi(shape)
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
def test_real_output():
    """C is real and the denominator is real, so S must be real up to round-off."""
    print("\n3. Real output (discarded imaginary part negligible)")
    rng = np.random.default_rng(2)
    ok = True
    for shape in SHAPES:
        st = _random_state(shape, rng)
        S, info = update_S(**st, return_info=True)
        ok &= check(
            f"shape {shape}",
            info["max_imag_rel"] <= 1e-14 and np.isrealobj(S),
            f"max|imag| = {info['max_imag']:.3e} "
            f"(relative {info['max_imag_rel']:.3e}), dtype {S.dtype}",
        )
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
        phi = compute_phi(shape)
        t_phi = time.perf_counter() - t0
        print(f"  compute_phi (once)   : {t_phi:8.2f} s")

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
        print("  Read-across to (g), where the full ADMM holds all of the above")
        print("  simultaneously plus HOOI factors and FFT temporaries:")
        print(f"    float64 as measured        : peak ~{peak:.0f} MB")
        print(f"    float32 would roughly halve : ~{peak/2:.0f} MB")
        print("    rfftn/irfftn would cut only the complex temporaries (~half of those)")
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
        test_real_output,
        test_beta_f_zero,
        test_sign_convention,
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
        print("Component (c) VERIFIED — all five tests pass.")
        return 0
    print("Component (c) NOT verified — fix before moving to (d).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
