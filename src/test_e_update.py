"""
Unit tests for Phase 1 component (e): the E-update (sparse noise).

Covers src/ssrtd_real.py -- update_E -- against paper/SOURCE.md eq. (12) and the
Appendix A derivation, eq. (17).

Five tests plus a memory probe:
  1. formula correctness   matches soft(X - L - S - mult_X/beta_X, 2/beta_X),
                           including a hand-computed case              (required)
  2. threshold constant    the realized radius is exactly 2/beta_X; factor 1.0
                           gives a materially different E; the gap is quantified
  3. argument identity     the argument is X - L - S - Lambda_X/beta_X, and is
                           distinguishable from the eq. (8) and eq. (9) residuals
  4. proximal optimality   REPORTS the eq. (17) stationarity gap at factor 1.0
                           and 2.0 -- deliberately measured, not asserted either
                           way; see below
  5. degenerate cases      beta_X large => E -> A; threshold > max|A| => E == 0

  memory probe             full-size (H,W,T) arrays: peak RSS and s/call.

WHY TEST 4 REPORTS RATHER THAN ASSERTS. eq. (12) prints threshold 2/beta_X
(verified against a rendered page image). Appendix A's eq. (17) reduces the
E-terms to  min_E ||E||_1 + (beta_X/2)||A - E||^2, whose proximal solution has
threshold 1/beta_X. The (beta/2) convention is present in eqs (15), (16) and
(17), so the factor 2 is not explained by an unusual Lagrangian scaling, and
Appendix A shows no shrinkage step for (12). The source paper is internally
inconsistent. We implement what is printed and measure the consequence rather
than silently "fixing" the equation. See PAPER_NOTES.md item 11.

The measurement has an exact prediction. For E_i != 0 the stationarity residual
of eq. (17) is
    sign(E_i) + beta_X (E_i - A_i) = sign(E_i) (1 - beta_X * tau) = sign(E_i)(1 - factor)
so the gap magnitude should be |1 - factor|: 0 at factor 1.0, 1 at factor 2.0.
Test 4 asserts the measurement matches that prediction, which makes it a real
test of our understanding rather than a bare print.

Run from the project directory as a module:
    python -m src.test_e_update
"""

import ctypes
import sys
from ctypes import wintypes

import numpy as np

from src.ssrtd_real import E_THRESHOLD_FACTOR, update_E
from src.tensor_rpca import soft_threshold

RTOL = 1e-12
SHAPES = [(5, 7, 3), (8, 3, 6), (4, 4, 4), (2, 5, 9)]

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def _state(shape, rng, beta_X=1.6):
    return dict(X=rng.standard_normal(shape), L=rng.standard_normal(shape),
                S=rng.standard_normal(shape), mult_X=rng.standard_normal(shape),
                beta_X=beta_X)


# ---------------------------------------------------------------- test 1
def test_formula_correctness():
    """E == soft(X - L - S - mult_X/beta_X, factor/beta_X)."""
    print("\n1. Formula correctness — eq. (12) as printed")
    rng = np.random.default_rng(0)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        E, info = update_E(**st, return_info=True)

        A = st["X"] - st["L"] - st["S"] - st["mult_X"] / st["beta_X"]
        expected = soft_threshold(A, E_THRESHOLD_FACTOR / st["beta_X"])
        worst = float(np.abs(E - expected).max())

        ok &= check(
            f"shape {shape}",
            worst == 0.0 and E.shape == shape,
            f"max|E - soft(A, 2/beta_X)| = {worst:.1e}; shape {E.shape}; "
            f"tau = {info['tau']:.4f}; zeros {info['zero_fraction']*100:.1f}%",
        )

    # hand-computed: L = S = mult_X = 0 so A = X exactly; beta_X = 1 => tau = 2
    shape = (2, 2, 2)
    X = np.zeros(shape)
    X.reshape(-1)[:6] = [0.0, 3.0, -3.0, 2.0, 1.5, 5.0]
    z = np.zeros(shape)
    E = update_E(X, z, z, z, beta_X=1.0)
    got = list(E.reshape(-1)[:6])
    want = [0.0, 1.0, -1.0, 0.0, 0.0, 3.0]
    ok &= check(
        "hand-computed case (beta_X=1, factor=2 => tau=2)",
        np.array_equal(got, want),
        f"A = [0, 3, -3, 2, 1.5, 5] -> E = {got}, expected {want}",
    )
    return ok


# ---------------------------------------------------------------- test 2
def test_threshold_constant():
    """The realized radius is exactly 2/beta_X, and factor 1.0 differs materially."""
    print("\n2. Threshold constant — 2/beta_X as printed, 1/beta_X compared")
    rng = np.random.default_rng(1)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        E2, i2 = update_E(**st, factor=2.0, return_info=True)
        E1, i1 = update_E(**st, factor=1.0, return_info=True)

        radius_ok = abs(i2["tau"] - 2.0 / st["beta_X"]) == 0.0
        # the realized shrinkage on surviving entries must equal tau
        nz = E2 != 0.0
        shrink = float(np.abs(np.abs(i2["A"][nz]) - np.abs(E2[nz]) - i2["tau"]).max())

        diff = float(np.abs(E2 - E1).max())
        ok &= check(
            f"shape {shape}",
            radius_ok and shrink <= 1e-14 and diff > 1e-6,
            f"tau = {i2['tau']:.6f} == 2/beta_X; realized shrinkage matches to "
            f"{shrink:.1e}; max|E(2.0) - E(1.0)| = {diff:.4f}; zeros "
            f"{i1['zero_fraction']*100:.1f}% -> {i2['zero_fraction']*100:.1f}%",
        )
    return ok


# ---------------------------------------------------------------- test 3
def test_argument_identity():
    """
    Three near-identical residuals appear across eqs (8), (9) and (12).

        eq. (8) : X - S - E - Lambda_X/beta_X
        eq. (9) : X - L - E
        eq. (12): X - L - S - Lambda_X/beta_X   <- this one

    Each is plausible and produces output; a mix-up runs cleanly.
    """
    print("\n3. Argument identity — the right residual out of three")
    rng = np.random.default_rng(2)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        E_prev = rng.standard_normal(shape)          # stand-in for a current E
        _, info = update_E(**st, return_info=True)

        eq12 = st["X"] - st["L"] - st["S"] - st["mult_X"] / st["beta_X"]
        eq8 = st["X"] - st["S"] - E_prev - st["mult_X"] / st["beta_X"]
        eq9 = st["X"] - st["L"] - E_prev

        exact = float(np.abs(info["A"] - eq12).max()) == 0.0
        d8 = float(np.abs(info["A"] - eq8).max())
        d9 = float(np.abs(info["A"] - eq9).max())

        ok &= check(
            f"shape {shape}",
            exact and d8 > 1e-6 and d9 > 1e-6,
            f"A == eq(12) residual exactly ({exact}); distance to eq(8) "
            f"residual {d8:.3f}, to eq(9) residual {d9:.3f} — both distinguishable",
        )

    # sign of the multiplier: divided by beta_X, and subtracted
    st = _state((5, 5, 5), rng)
    _, info = update_E(**st, return_info=True)
    flipped = st["X"] - st["L"] - st["S"] + st["mult_X"] / st["beta_X"]
    scaled = st["X"] - st["L"] - st["S"] - st["mult_X"] * st["beta_X"]
    ok &= check(
        "multiplier enters as -Lambda_X/beta_X (not +, not *beta_X)",
        float(np.abs(info["A"] - flipped).max()) > 1e-6
        and float(np.abs(info["A"] - scaled).max()) > 1e-6,
        f"distance to sign-flipped {float(np.abs(info['A'] - flipped).max()):.3f}, "
        f"to beta_X-multiplied {float(np.abs(info['A'] - scaled).max()):.3f}",
    )
    return ok


# ---------------------------------------------------------------- test 4
def test_proximal_optimality_report():
    """
    MEASURE the eq. (17) stationarity gap at factor 1.0 and 2.0.

    Predicted: for E_i != 0 the residual is sign(E_i)(1 - factor), so the gap
    magnitude is |1 - factor| -- 0 at 1.0 and 1 at 2.0. Asserting that the
    measurement matches the prediction tests our understanding; it does not
    assert which factor the paper intended.
    """
    print("\n4. Proximal optimality vs eq. (17) — MEASURED at both factors")
    print("     eq. (17):  min_E ||E||_1 + (beta_X/2)||A - E||^2")
    print("     stationarity residual on E != 0:  sign(E) + beta_X(E - A)")
    rng = np.random.default_rng(3)
    ok = True

    for shape in SHAPES[:3]:
        st = _state(shape, rng)
        line = []
        measured = {}
        for factor in (1.0, 2.0):
            E, info = update_E(**st, factor=factor, return_info=True)
            A, beta_X = info["A"], st["beta_X"]

            nz = E != 0.0
            resid = np.sign(E[nz]) + beta_X * (E[nz] - A[nz])
            gap = float(np.abs(resid).max()) if nz.any() else 0.0

            # entries zeroed that eq. (17) optimality would keep: |A| > 1/beta_X
            over = int(np.sum((~nz) & (np.abs(A) > 1.0 / beta_X)))
            measured[factor] = gap
            line.append(f"factor {factor}: gap {gap:.3e}, "
                        f"{over} entries zeroed beyond the eq.(17) radius")

        as_predicted = (measured[1.0] <= 1e-14
                        and abs(measured[2.0] - 1.0) <= 1e-12)
        ok &= check(
            f"shape {shape}",
            as_predicted,
            " | ".join(line) + f"  [predicted |1 - factor|: 0.0 and 1.0]",
        )

    print("     ---")
    print("     Reading: factor 1.0 satisfies eq. (17) optimality exactly;")
    print("     factor 2.0 leaves a unit-magnitude stationarity residual on every")
    print("     surviving entry. Recorded, not acted on -- eq. (12) is implemented")
    print("     as printed and the choice is resolved by measurement at (g).")
    return ok


# ---------------------------------------------------------------- test 5
def test_degenerate_cases():
    """Exact analytic endpoints."""
    print("\n5. Degenerate cases")
    rng = np.random.default_rng(4)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)

        # threshold above max|A| zeroes everything
        _, i0 = update_E(**st, return_info=True)
        big = float(np.abs(i0["A"]).max()) * st["beta_X"] * 1.001
        Ebig = update_E(**st, factor=big)
        all_zero = float(np.abs(Ebig).max()) == 0.0

        # large beta_X shrinks the threshold to nothing: E -> A
        st_big = dict(st, beta_X=1e9)
        Ebeta, ib = update_E(**st_big, return_info=True)
        approaches = float(np.abs(Ebeta - ib["A"]).max()) < 1e-8

        ok &= check(
            f"shape {shape}",
            all_zero and approaches,
            f"tau > max|A| -> E == 0 exactly ({all_zero}); "
            f"beta_X = 1e9 -> max|E - A| = "
            f"{float(np.abs(Ebeta - ib['A']).max()):.2e} ({approaches})",
        )

    st = _state((6, 5, 4), rng)
    zeros = []
    for factor in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0):
        _, info = update_E(**st, factor=factor, return_info=True)
        zeros.append(info["zero_fraction"])
    monotone = all(b >= a for a, b in zip(zeros, zeros[1:]))
    ok &= check(
        "zero fraction increases monotonically with the threshold",
        monotone and zeros[0] == 0.0 and zeros[-1] > zeros[0],
        f"factor 0 -> 8: {[f'{z*100:.1f}%' for z in zeros]}",
    )

    try:
        update_E(**dict(st, beta_X=0.0))
        fired = False
    except ValueError:
        fired = True
    ok &= check("beta_X = 0 raises", fired, "beta_X must be strictly positive")
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
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_MEMCOUNTERS), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    c = _MEMCOUNTERS()
    c.cb = ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError(f"GetProcessMemoryInfo failed ({ctypes.get_last_error()})")
    return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20


def memory_probe():
    print("\n" + "-" * 72)
    print("MEMORY PROBE — full-size (H,W,T) arrays, float64")
    print("-" * 72)
    try:
        import time
        shape = (180, 320, 300)
        one = int(np.prod(shape)) * 8 / 2**20
        base_cur, base_peak = _mem_mb()
        print(f"  shape {shape}: {one:.0f} MB per tensor "
              f"(E lives in (H,W,T), unlike f)")
        print(f"  baseline working set : {base_cur:8.0f} MB "
              f"(peak so far {base_peak:.0f} MB)")

        rng = np.random.default_rng(0)
        st = dict(X=rng.standard_normal(shape), L=rng.standard_normal(shape),
                  S=rng.standard_normal(shape), mult_X=rng.standard_normal(shape),
                  beta_X=1.6)
        after, _ = _mem_mb()
        print(f"  after X,L,S,Lambda_X : {after:8.0f} MB  (4 x {one:.0f} MB)")

        t0 = time.perf_counter()
        E = update_E(**st)
        dt = time.perf_counter() - t0
        cur, peak = _mem_mb()

        print(f"  update_E             : {dt:8.2f} s/call")
        print(f"  working set now      : {cur:8.0f} MB")
        print(f"  PEAK working set     : {peak:8.0f} MB   "
              f"<-- headroom against 8 GB: {8192 - peak:.0f} MB")
        print(f"  E: zeros {float(np.mean(E == 0))*100:.1f}%")
        print()
        print("  Compare: (c) S-update peak 2,840 MB, (d) f-update peak 2,181 MB.")
        return True
    except Exception as exc:
        print(f"  probe skipped: {type(exc).__name__}: {exc}")
        return True


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (e) — E-update (sparse noise)")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (12), Appendix A eq. (17)")
    print(f"numpy {np.__version__}   E_THRESHOLD_FACTOR = {E_THRESHOLD_FACTOR}")
    print("=" * 72)

    tests = [
        test_formula_correctness,
        test_threshold_constant,
        test_argument_identity,
        test_proximal_optimality_report,
        test_degenerate_cases,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{len(_results)} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    memory_probe()

    print()
    if all(outcomes):
        print("Component (e) VERIFIED — all five tests pass.")
        return 0
    print("Component (e) NOT verified — fix before moving to (f).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
