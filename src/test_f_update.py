"""
Unit tests for Phase 1 component (d): the f-update (TV auxiliary).

Covers src/ssrtd_real.py -- update_f -- against paper/SOURCE.md eq. (10), (11).

Five tests plus a memory probe:
  1. formula correctness   matches soft(D vec(S) + mult_f/beta_f, lam/beta_f)
                           including a hand-computed case                (required)
  2. proximal optimality   f actually MINIMIZES eq. (10), checked by the
                           subgradient condition and by brute force
  3. lambda collision      a lam <-> mult_f swap is DETECTED, and the guards fire
  4. anisotropy            thresholding is element-wise, not grouped across
                           the three stacked difference components
  5. degenerate cases      lam = 0 => f == A; huge threshold => f == 0

  memory probe             full-size (3,180,320,300) arrays: peak RSS.

Test 3 is the important one. Swapping the scalar tuning parameter `lam` with the
(3,H,W,T) multiplier `mult_f` broadcasts cleanly in NumPy -- a scalar shift and
an array threshold are both legal -- so the swapped call returns a correctly
shaped, entirely wrong f with no error. Asserting that the correct formula works
does not catch that; asserting the swap produces a DIFFERENT answer does.

Run from the project directory as a module:
    python -m src.test_f_update
"""

import ctypes
import sys
from ctypes import wintypes

import numpy as np

from src.ssrtd_real import tv_forward, update_f
from src.tensor_rpca import soft_threshold, soft_threshold_inplace

RTOL = 1e-12
SHAPES = [(5, 7, 3), (8, 3, 6), (4, 4, 4), (2, 5, 9)]

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def _state(shape, rng, lam=0.6, beta_f=1.4):
    return dict(S=rng.standard_normal(shape),
                mult_f=rng.standard_normal((3,) + shape),
                lam=lam, beta_f=beta_f)


# ---------------------------------------------------------------- test 1
def test_formula_correctness():
    """f == soft(D vec(S) + mult_f/beta_f, lam/beta_f), element-wise."""
    print("\n1. Formula correctness — eq. (11)")
    rng = np.random.default_rng(0)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        f, info = update_f(**st, return_info=True)

        A = tv_forward(st["S"]) + st["mult_f"] / st["beta_f"]
        expected = soft_threshold(A, st["lam"] / st["beta_f"])
        worst = float(np.abs(f - expected).max())

        ok &= check(
            f"shape {shape}",
            worst == 0.0 and f.shape == (3,) + shape,
            f"max|f - soft(A, lam/beta_f)| = {worst:.1e}; shape {f.shape}; "
            f"tau = {info['tau']:.4f}; zeros {info['zero_fraction']*100:.1f}%",
        )

    # hand-computed case: S = 0 so A = mult_f/beta_f exactly
    shape = (2, 2, 2)
    beta_f, lam = 2.0, 4.0                       # tau = 2.0
    mult_f = np.zeros((3,) + shape)
    flat = mult_f.reshape(-1)
    flat[:6] = [0.0, 6.0, -6.0, 4.0, 3.0, 10.0]  # A = 0, 3, -3, 2, 1.5, 5
    f = update_f(np.zeros(shape), mult_f, lam, beta_f)
    got = list(f.reshape(-1)[:6])
    want = [0.0, 1.0, -1.0, 0.0, 0.0, 3.0]
    ok &= check(
        "hand-computed case (beta_f=2, lam=4 => tau=2)",
        np.array_equal(got, want),
        f"A = [0, 3, -3, 2, 1.5, 5] -> f = {got}, expected {want}",
    )
    return ok


# ---------------------------------------------------------------- test 2
def test_proximal_optimality():
    """
    f must MINIMIZE eq. (10), not merely match the closed form.

    Subgradient condition for  min_f  lam*||f||_1 + (beta_f/2)||f - A||^2 :
        f_i != 0 :  beta_f*(f_i - A_i) + lam*sign(f_i) == 0
        f_i == 0 :  |A_i| <= lam/beta_f
    """
    print("\n2. Proximal optimality — f minimizes eq. (10)")
    rng = np.random.default_rng(1)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        f, info = update_f(**st, return_info=True)
        A, lam, beta_f = info["A"], st["lam"], st["beta_f"]

        nz = f != 0.0
        stat = beta_f * (f[nz] - A[nz]) + lam * np.sign(f[nz])
        worst_stat = float(np.abs(stat).max()) if nz.any() else 0.0

        z = ~nz
        worst_zero = float((np.abs(A[z]) - info["tau"]).max()) if z.any() else -1.0

        ok &= check(
            f"shape {shape}",
            worst_stat <= 1e-14 and worst_zero <= 1e-14,
            f"nonzero: max|beta_f(f-A) + lam*sign(f)| = {worst_stat:.2e} "
            f"({nz.sum()} entries); zero: max(|A| - tau) = {worst_zero:+.2e} "
            f"({z.sum()} entries, must be <= 0)",
        )

    # brute force on a handful of elements: dense grid + refinement
    lam, beta_f = 0.6, 1.4
    A_vals = np.array([-3.0, -0.4, 0.0, 0.25, 0.9, 2.7])
    mult_f = np.zeros((3, 2, 3, 1))
    mult_f.reshape(-1)[:6] = A_vals * beta_f            # S = 0 => A = mult_f/beta_f
    f = update_f(np.zeros((2, 3, 1)), mult_f, lam, beta_f).reshape(-1)[:6]

    def objective(x, a):
        return lam * abs(x) + 0.5 * beta_f * (x - a) ** 2

    worst = 0.0
    for a, got in zip(A_vals, f):
        grid = np.linspace(a - 5, a + 5, 200001)
        best = grid[np.argmin(objective(grid, a))]
        worst = max(worst, abs(best - got))
    ok &= check(
        "brute-force grid minimization agrees",
        worst < 1e-4,
        f"max|argmin_grid - f| = {worst:.2e} over A = {list(A_vals)} "
        f"(grid resolution 5e-5)",
    )
    return ok


# ---------------------------------------------------------------- test 3
def test_lambda_collision():
    """A lam <-> mult_f swap must be detected, and the guards must fire."""
    print("\n3. Lambda collision — swap is detected, guards fire")
    rng = np.random.default_rng(2)
    ok = True
    shape = (5, 7, 3)
    st = _state(shape, rng)
    f = update_f(**st)

    # the swapped formula: shift by the SCALAR, threshold by the ARRAY.
    # NumPy broadcasts this happily -- no error, correct shape, wrong answer.
    swapped = soft_threshold(tv_forward(st["S"]) + st["lam"] / st["beta_f"],
                             st["mult_f"] / st["beta_f"])
    diff = float(np.abs(f - swapped).max())
    ok &= check(
        "swapped formula runs cleanly but differs materially",
        swapped.shape == f.shape and diff > 1e-3,
        f"swapped result has identical shape {swapped.shape} and raises nothing; "
        f"max|correct - swapped| = {diff:.4f}",
    )

    # guards
    try:
        update_f(st["S"], st["mult_f"], st["mult_f"], st["beta_f"])
        fired_a = False
    except ValueError:
        fired_a = True
    ok &= check("passing the multiplier as `lam` raises", fired_a,
                "caught by the scalar check on lam")

    try:
        update_f(st["S"], st["lam"], st["lam"], st["beta_f"])
        fired_b = False
    except ValueError:
        fired_b = True
    ok &= check("passing the scalar as `mult_f` raises", fired_b,
                "caught by the shape check on mult_f")

    try:
        update_f(st["S"], rng.standard_normal((3,) + (4, 4, 4)), st["lam"], st["beta_f"])
        fired_c = False
    except ValueError:
        fired_c = True
    ok &= check("wrong-shaped mult_f raises", fired_c, "shape must match D vec(S)")

    try:
        update_f(st["S"], st["mult_f"], st["lam"], 0.0)
        fired_d = False
    except ValueError:
        fired_d = True
    ok &= check("beta_f = 0 raises", fired_d, "beta_f must be strictly positive")

    # lam moves only the threshold; mult_f moves only the argument
    _, i1 = update_f(**{**st, "lam": st["lam"]}, return_info=True)
    _, i2 = update_f(**{**st, "lam": st["lam"] * 3}, return_info=True)
    lam_only_threshold = (float(np.abs(i1["A"] - i2["A"]).max()) == 0.0
                          and i2["tau"] > i1["tau"]
                          and i2["zero_fraction"] > i1["zero_fraction"])
    ok &= check(
        "scaling lam changes the threshold, not the argument",
        lam_only_threshold,
        f"A unchanged; tau {i1['tau']:.4f} -> {i2['tau']:.4f}; "
        f"zeros {i1['zero_fraction']*100:.1f}% -> {i2['zero_fraction']*100:.1f}%",
    )

    _, i3 = update_f(**{**st, "mult_f": st["mult_f"] + 2.0}, return_info=True)
    shift_only_arg = (abs(i3["tau"] - i1["tau"]) == 0.0
                      and np.allclose(i3["A"] - i1["A"], 2.0 / st["beta_f"]))
    ok &= check(
        "shifting mult_f changes the argument, not the threshold",
        shift_only_arg,
        f"tau unchanged at {i1['tau']:.4f}; A shifted by exactly "
        f"2/beta_f = {2.0/st['beta_f']:.6f}",
    )
    return ok


# ---------------------------------------------------------------- test 4
def test_anisotropy():
    """Element-wise, not grouped: this is what makes it ANISOTROPIC TV."""
    print("\n4. Anisotropy — element-wise, not grouped across (f_h, f_v, f_t)")
    rng = np.random.default_rng(3)
    ok = True
    for shape in SHAPES[:2]:
        st = _state(shape, rng)
        f, info = update_f(**st, return_info=True)

        # each stacked component depends only on its own slice of A
        per_component = np.stack(
            [soft_threshold(info["A"][k], info["tau"]) for k in range(3)], axis=0)
        independent = float(np.abs(f - per_component).max()) == 0.0

        # perturbing component 0 must leave 1 and 2 bit-identical
        pert = st["mult_f"].copy()
        pert[0] += 5.0
        f2 = update_f(st["S"], pert, st["lam"], st["beta_f"])
        untouched = (np.array_equal(f[1], f2[1]) and np.array_equal(f[2], f2[2]))
        changed = not np.array_equal(f[0], f2[0])

        ok &= check(
            f"shape {shape}",
            independent and untouched and changed,
            f"per-component soft-threshold identical = {independent}; "
            f"perturbing component 0 left 1 and 2 bit-identical = {untouched}, "
            f"changed component 0 = {changed}",
        )

    # distinguish from isotropic: group shrinkage would give a different answer
    shape = (3, 3, 2)
    st = _state(shape, rng, lam=1.0, beta_f=1.0)
    f, info = update_f(**st, return_info=True)
    A, tau = info["A"], info["tau"]
    norms = np.sqrt((A ** 2).sum(axis=0, keepdims=True))
    isotropic = A * np.maximum(1.0 - tau / np.maximum(norms, 1e-300), 0.0)
    differs = float(np.abs(f - isotropic).max()) > 1e-6
    ok &= check(
        "anisotropic result differs from isotropic group shrinkage",
        differs,
        f"max|anisotropic - isotropic| = {float(np.abs(f - isotropic).max()):.4f} "
        f"(Algorithm 1 line 4 specifies anisotropic)",
    )
    return ok


# ---------------------------------------------------------------- test 5
def test_degenerate_cases():
    """Exact analytic endpoints at lam = 0 and at a threshold above max|A|."""
    print("\n5. Degenerate cases")
    rng = np.random.default_rng(4)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)

        f0, i0 = update_f(**{**st, "lam": 0.0}, return_info=True)
        no_shrink = float(np.abs(f0 - i0["A"]).max()) == 0.0

        big = float(np.abs(i0["A"]).max()) * st["beta_f"] * 1.001
        fbig = update_f(**{**st, "lam": big})
        all_zero = float(np.abs(fbig).max()) == 0.0

        ok &= check(
            f"shape {shape}",
            no_shrink and all_zero,
            f"lam=0 -> f == A exactly ({no_shrink}); "
            f"lam/beta_f > max|A| -> f == 0 exactly ({all_zero})",
        )

    # sparsity must increase monotonically with lam
    st = _state((6, 5, 4), rng)
    zeros = []
    for lam in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        _, info = update_f(**{**st, "lam": lam}, return_info=True)
        zeros.append(info["zero_fraction"])
    monotone = all(b >= a for a, b in zip(zeros, zeros[1:]))
    ok &= check(
        "zero fraction increases monotonically with lam",
        monotone and zeros[0] == 0.0 and zeros[-1] > zeros[0],
        f"lam 0 -> 4: {[f'{z*100:.1f}%' for z in zeros]}",
    )
    return ok


# ---------------------------------------------------------------- test 6
def test_inplace_soft_threshold():
    """
    Memory lever A: update_f now thresholds A in place. The in-place helper must
    be BITWISE identical to soft_threshold -- values, dtype, and the sign of
    every zero -- and must actually consume its input rather than copy it.
    """
    print("\n6. In-place soft-threshold == soft_threshold, bitwise (memory lever A)")
    rng = np.random.default_rng(6)
    ok = True
    for shape in SHAPES + [(6, 8, 11)]:
        A = rng.standard_normal((3,) + shape)
        A.reshape(-1)[:7] = [0.0, -0.0, 0.3, -0.3, 1.0, -1.0, 5.0]   # edge cases
        for tau in (0.0, 0.3, 0.7, 9.0):
            ref = soft_threshold(A, tau)
            work = A.copy()
            out = soft_threshold_inplace(work, tau)

            same_bits = (ref.tobytes() == out.tobytes())          # incl. -0.0 vs 0.0
            same_signbit = bool(np.array_equal(np.signbit(ref), np.signbit(out)))
            consumed = out is work
            ok &= check(
                f"shape {shape}, tau {tau}",
                same_bits and same_signbit and consumed and out.dtype == ref.dtype,
                f"bytes identical={same_bits}, signbit identical={same_signbit}, "
                f"returns its input={consumed}, zeros {100*np.mean(out == 0):.0f}%",
            )

    # end to end: update_f still equals the closed form exactly (test 1 covers the
    # formula; this pins that the in-place path is the one actually taken)
    st = _state((5, 7, 3), rng)
    f, info = update_f(**st, return_info=True)
    expected = soft_threshold(info["A"], st["lam"] / st["beta_f"])
    ok &= check(
        "update_f output bitwise equals soft_threshold(A, tau); info['A'] is a pre-threshold copy",
        f.tobytes() == expected.tobytes()
        and float(np.abs(info["A"]).max()) >= float(np.abs(f).max()),
        f"max|f - expected| = {float(np.abs(f - expected).max()):.1e}; "
        f"max|A| {float(np.abs(info['A']).max()):.4f} >= max|f| {float(np.abs(f).max()):.4f}",
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
    """(current, peak) working set in MB. argtypes are required -- see (c)."""
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
    """(3,H,W,T) arrays are the largest in the algorithm -- measure the real peak."""
    print("\n" + "-" * 72)
    print("MEMORY PROBE — full-size stacked arrays, float64")
    print("-" * 72)
    try:
        import time
        shape = (180, 320, 300)
        one = int(np.prod(shape)) * 8 / 2**20
        base_cur, base_peak = _mem_mb()
        print(f"  shape {shape}: {one:.0f} MB per (H,W,T), "
              f"{3*one:.0f} MB per (3,H,W,T)")
        print(f"  baseline working set : {base_cur:8.0f} MB "
              f"(peak so far {base_peak:.0f} MB)")

        rng = np.random.default_rng(0)
        S = rng.standard_normal(shape)
        mult_f = rng.standard_normal((3,) + shape)
        after, _ = _mem_mb()
        print(f"  after S + mult_f     : {after:8.0f} MB")

        t0 = time.perf_counter()
        f = update_f(S, mult_f, 0.4, 1.4)
        dt = time.perf_counter() - t0
        cur, peak = _mem_mb()

        print(f"  update_f             : {dt:8.2f} s/call")
        print(f"  working set now      : {cur:8.0f} MB")
        print(f"  PEAK working set     : {peak:8.0f} MB   "
              f"<-- headroom against 8 GB: {8192 - peak:.0f} MB")
        print(f"  f: shape {f.shape}, zeros {float(np.mean(f == 0))*100:.1f}%")
        print()
        print("  update_f transiently holds mult_f + tv_forward(S) + result")
        print(f"  = 3 x {3*one:.0f} MB of stacked arrays. Compare (c)'s 2,840 MB peak.")
        return True
    except Exception as exc:
        print(f"  probe skipped: {type(exc).__name__}: {exc}")
        return True


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (d) — f-update (TV auxiliary)")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (10), (11)")
    print(f"numpy {np.__version__}   rtol {RTOL:g}")
    print("=" * 72)

    tests = [
        test_formula_correctness,
        test_proximal_optimality,
        test_lambda_collision,
        test_anisotropy,
        test_degenerate_cases,
        test_inplace_soft_threshold,
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
        print("Component (d) VERIFIED — all six tests pass.")
        return 0
    print("Component (d) NOT verified — fix before moving to (e).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
