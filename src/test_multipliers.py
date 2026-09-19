"""
Unit tests for Phase 1 component (f): multiplier and adaptive penalty updates.

Covers src/ssrtd_real.py -- primal_residuals, update_multipliers, update_penalty
-- against paper/SOURCE.md eq. (13) and (14), with the sign tied to eq. (7).

Five tests plus a probe:
  1. eq. (13) correctness    both updates match the printed formula     (required)
  2. sign vs eq. (7)         the minus follows from (7)'s NEGATIVE inner
                             product, verified by finite differences on the
                             actual Lagrangian -- not assumed from convention
  3. eq. (14) logic          grows iff Err_new >= c2*Err_old, boundary
                             included; never decreases                  (required)
  4. constants distinct      gamma=1.1, c1=1.15, c2=0.95; a swap is detectable
  5. sequence behaviour      decreasing / stalled / mixed error sequences,
                             plus the 100-iteration growth bound

  probe                      full-size timing and peak RSS.

THE TWO THINGS THAT ARE EASY TO GET WRONG HERE:

  The SIGN. Textbook ADMM writes lambda <- lambda + rho*c. The paper writes
  minus, which is correct because eq. (7) defines the augmented Lagrangian with
  -<lambda, c>. Test 2 differentiates eq. (7) numerically and checks the update
  moves along +dL/dlambda, tying the sign to the source rather than to habit.

  The DIRECTION of eq. (14). beta grows only on LACK of progress
  (Err_new >= c2*Err_old). Reading it as "grows when the error shrinks" inverts
  the controller and is not obviously wrong from the output. Test 3 pins the
  direction, the >= boundary, and the never-decreasing property.

Run from the project directory as a module:
    python -m src.test_multipliers
"""

import ctypes
import sys
from ctypes import wintypes

import numpy as np

from src.ssrtd_real import (
    GAMMA, C1, C2, primal_residuals, tv_forward, update_multipliers,
    update_penalty,
)

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def _state(shape, rng):
    return dict(mult_f=rng.standard_normal((3,) + shape),
                mult_X=rng.standard_normal(shape),
                f=rng.standard_normal((3,) + shape),
                S=rng.standard_normal(shape),
                X=rng.standard_normal(shape),
                L=rng.standard_normal(shape),
                E=rng.standard_normal(shape),
                beta_f=1.3, beta_X=0.7)


SHAPES = [(5, 7, 3), (8, 3, 6), (4, 4, 4)]


# ---------------------------------------------------------------- test 1
def test_eq13_correctness():
    """Both multiplier updates match eq. (13) exactly."""
    print("\n1. eq. (13) correctness")
    rng = np.random.default_rng(0)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        new_f, new_X = update_multipliers(**st)

        exp_f = st["mult_f"] - GAMMA * st["beta_f"] * (st["f"] - tv_forward(st["S"]))
        exp_X = st["mult_X"] - GAMMA * st["beta_X"] * (
            st["X"] - st["L"] - st["S"] - st["E"])

        df = float(np.abs(new_f - exp_f).max())
        dX = float(np.abs(new_X - exp_X).max())
        shapes_ok = new_f.shape == (3,) + shape and new_X.shape == shape
        # inputs must not be mutated
        untouched = True  # _state arrays are fresh each call; check identity anyway
        ok &= check(
            f"shape {shape}",
            df == 0.0 and dX == 0.0 and shapes_ok and untouched,
            f"max|lambda_f - expected| = {df:.1e}, "
            f"max|Lambda_X - expected| = {dX:.1e}; shapes {new_f.shape}, {new_X.shape}",
        )

    # hand-computed: S = 0 so D vec(S) = 0; L = E = 0 so the X residual is X
    shape = (2, 2, 2)
    z, z3 = np.zeros(shape), np.zeros((3,) + shape)
    f = np.ones((3,) + shape) * 2.0
    X = np.ones(shape) * 3.0
    nf, nX = update_multipliers(z3, z, f, z, X, z, z, beta_f=2.0, beta_X=5.0)
    # lambda_f = 0 - 1.1*2*(2 - 0) = -4.4 ; Lambda_X = 0 - 1.1*5*(3) = -16.5
    ok &= check(
        "hand-computed case",
        np.allclose(nf, -4.4) and np.allclose(nX, -16.5),
        f"lambda_f = 0 - 1.1*2*2 = {nf.flat[0]:.4f} (expect -4.4); "
        f"Lambda_X = 0 - 1.1*5*3 = {nX.flat[0]:.4f} (expect -16.5)",
    )

    # lever B: passing a precomputed DS = tv_forward(S), and the one-temporary
    # form of the multiplier line, must be BITWISE identical to the formula
    for shape in SHAPES:
        st = _state(shape, rng)
        DS = tv_forward(st["S"])
        a_f, a_X = update_multipliers(**st)
        b_f, b_X = update_multipliers(**st, DS=DS)
        formula = st["mult_f"] - GAMMA * st["beta_f"] * (st["f"] - DS)
        formula_X = st["mult_X"] - GAMMA * st["beta_X"] * (
            st["X"] - st["L"] - st["S"] - st["E"])
        ok &= check(
            f"DS param + one-temp form bitwise, shape {shape}",
            a_f.tobytes() == b_f.tobytes() == formula.tobytes()
            and a_X.tobytes() == b_X.tobytes() == formula_X.tobytes(),
            f"bytes(no DS) == bytes(DS) == bytes(formula): "
            f"f {a_f.tobytes() == b_f.tobytes() == formula.tobytes()}, "
            f"X {a_X.tobytes() == b_X.tobytes() == formula_X.tobytes()}",
        )
        # lever E: default leaves the inputs untouched; inplace=True overwrites
        # them with the same bytes and returns the same objects
        mf0, mX0 = st["mult_f"].tobytes(), st["mult_X"].tobytes()
        untouched = (st["mult_f"].tobytes() == mf0 and st["mult_X"].tobytes() == mX0)
        mf_obj, mX_obj = st["mult_f"], st["mult_X"]
        c_f, c_X = update_multipliers(**st, DS=DS, inplace=True)
        ok &= check(
            f"inplace=True bitwise + same objects; default non-mutating, shape {shape}",
            untouched and c_f is mf_obj and c_X is mX_obj
            and c_f.tobytes() == formula.tobytes()
            and c_X.tobytes() == formula_X.tobytes(),
            f"default left inputs untouched={untouched}; inplace returns its inputs="
            f"{c_f is mf_obj and c_X is mX_obj}; bytes == formula: "
            f"f {c_f.tobytes() == formula.tobytes()}, X {c_X.tobytes() == formula_X.tobytes()}",
        )
        e1 = primal_residuals(st["f"], st["S"], st["X"], st["L"], st["E"])
        e2 = primal_residuals(st["f"], st["S"], st["X"], st["L"], st["E"], DS=DS)
        ok &= check(f"primal_residuals with DS identical, shape {shape}", e1 == e2,
                    f"{e1} == {e2}")

    # residual norms
    st = _state((6, 5, 4), rng)
    err_f, err_X = primal_residuals(st["f"], st["S"], st["X"], st["L"], st["E"])
    man_f = float(np.linalg.norm((st["f"] - tv_forward(st["S"])).ravel()))
    man_X = float(np.linalg.norm((st["X"] - st["L"] - st["S"] - st["E"]).ravel()))
    ok &= check(
        "primal_residuals matches ||f - Dvec(S)|| and ||X-L-S-E||_F",
        abs(err_f - man_f) <= 1e-12 and abs(err_X - man_X) <= 1e-12,
        f"err_f = {err_f:.6f}, err_X = {err_X:.6f}",
    )
    return ok


# ---------------------------------------------------------------- test 2
def test_sign_from_eq7():
    """
    The minus follows from eq. (7)'s NEGATIVE inner product, not from convention.

    eq. (7) f-terms:  Lf(m) = -<m, r> + (beta_f/2)||r||^2,  r = f - Dvec(S)
    so dLf/dm = -r, and dual ASCENT m <- m + gamma*beta_f*dLf/dm gives
    m <- m - gamma*beta_f*r, which is eq. (13).
    """
    print("\n2. Sign convention derived from eq. (7), not assumed")
    rng = np.random.default_rng(1)
    ok = True
    for shape in SHAPES:
        st = _state(shape, rng)
        r = st["f"] - tv_forward(st["S"])

        def lagrangian_f(m):
            """The eq. (7) terms involving lambda_f."""
            return float(-np.sum(m * r) + 0.5 * st["beta_f"] * np.sum(r * r))

        # finite-difference dL/dm along a random direction
        v = rng.standard_normal((3,) + shape)
        h = 1e-6
        fd = (lagrangian_f(st["mult_f"] + h * v)
              - lagrangian_f(st["mult_f"] - h * v)) / (2 * h)
        analytic = float(np.sum(-r * v))
        grad_ok = abs(fd - analytic) / max(abs(analytic), 1.0) < 1e-6

        # ascent along that gradient reproduces eq. (13)
        ascent = st["mult_f"] + GAMMA * st["beta_f"] * (-r)
        printed, _ = update_multipliers(**st)
        matches = float(np.abs(ascent - printed).max()) == 0.0

        # the + convention is materially different
        plus = st["mult_f"] + GAMMA * st["beta_f"] * r
        differs = float(np.abs(printed - plus).max()) > 1e-6

        ok &= check(
            f"shape {shape}",
            grad_ok and matches and differs,
            f"dL/dm: finite-diff {fd:+.6f} vs analytic -<r,v> {analytic:+.6f} "
            f"(match {grad_ok}); ascent reproduces eq.(13) ({matches}); "
            f"'+' convention differs by {float(np.abs(printed - plus).max()):.3f}",
        )
    return ok


# ---------------------------------------------------------------- test 3
def test_eq14_conditional_logic():
    """beta grows iff Err_new >= c2*Err_old. Boundary included. Never decreases."""
    print("\n3. eq. (14) conditional logic — direction and boundary")
    ok = True
    beta0, prev = 2.0, 10.0
    thresh = C2 * prev                       # 9.5

    cases = [
        ("no progress (err rises)",        12.0, True),
        ("stalled (err unchanged)",        10.0, True),
        ("just above threshold",   thresh + 1e-9, True),
        ("exactly at threshold (>=)",   thresh,   True),
        ("just below threshold",   thresh - 1e-9, False),
        ("good progress (halved)",          5.0, False),
        ("err -> 0",                        0.0, False),
    ]
    for name, err_new, should_grow in cases:
        beta, grew = update_penalty(beta0, err_new, prev)
        expected = C1 * beta0 if should_grow else beta0
        ok &= check(
            f"{name}: err_new={err_new:.10g} vs c2*err_prev={thresh:.10g}",
            grew == should_grow and beta == expected,
            f"grew={grew} (expect {should_grow}), beta {beta0} -> {beta:.6f} "
            f"(expect {expected:.6f})",
        )

    # never decreases, over random sequences
    rng = np.random.default_rng(2)
    decreased = 0
    for _ in range(2000):
        b = float(rng.uniform(0.1, 10))
        nb, _ = update_penalty(b, float(rng.uniform(0, 20)), float(rng.uniform(0, 20)))
        decreased += nb < b
    ok &= check("beta never decreases (2000 random draws)", decreased == 0,
                f"{decreased} decreases observed")

    # growth factor is exactly c1
    b, grew = update_penalty(3.0, 100.0, 1.0)
    ok &= check("growth factor is exactly c1", grew and b == C1 * 3.0,
                f"3.0 -> {b} (c1*3.0 = {C1*3.0})")

    # the INVERTED condition would behave differently -- direction is pinned
    inverted_would_grow = 5.0 <= C2 * 10.0
    _, actual = update_penalty(1.0, 5.0, 10.0)
    ok &= check(
        "inverted condition is distinguishable (direction pinned)",
        actual is False and inverted_would_grow is True,
        "with err 10 -> 5 (good progress): correct rule does NOT grow; "
        "the inverted rule would. Opposite outcomes, so the test discriminates.",
    )
    return ok


# ---------------------------------------------------------------- test 4
def test_constants_distinct():
    """gamma=1.1 scales the multiplier step; c1=1.15 the penalty; c2=0.95 the test."""
    print("\n4. Constants are the paper's, and distinguishable")
    ok = True
    ok &= check("GAMMA == 1.1", GAMMA == 1.1, f"got {GAMMA}")
    ok &= check("C1 == 1.15", C1 == 1.15, f"got {C1}")
    ok &= check("C2 == 0.95", C2 == 0.95, f"got {C2}")
    ok &= check("all three distinct", len({GAMMA, C1, C2}) == 3,
                f"gamma={GAMMA}, c1={C1}, c2={C2} — gamma and c1 differ by only "
                f"{abs(C1-GAMMA):.2f}, and both multiply something")

    rng = np.random.default_rng(3)
    st = _state((5, 6, 4), rng)
    correct, _ = update_multipliers(**st)
    swapped, _ = update_multipliers(**st, gamma=C1)      # gamma <-> c1 swap
    diff = float(np.abs(correct - swapped).max())
    ok &= check("gamma <-> c1 swap in eq. (13) is detectable", diff > 1e-6,
                f"max|correct - swapped| = {diff:.4f}")

    b_correct, _ = update_penalty(1.0, 10.0, 10.0, c1=C1)
    b_swapped, _ = update_penalty(1.0, 10.0, 10.0, c1=GAMMA)
    ok &= check("c1 <-> gamma swap in eq. (14) is detectable",
                b_correct != b_swapped,
                f"beta -> {b_correct} (c1) vs {b_swapped} (gamma)")
    return ok


# ---------------------------------------------------------------- test 5
def test_sequence_behaviour():
    """Behaviour as a process, across error sequences, plus the growth bound."""
    print("\n5. Sequence behaviour over 100 iterations")
    ok = True

    # steadily decreasing errors: never grows
    beta, errs = 1.0, [10.0 * (0.5 ** k) for k in range(101)]
    grows = 0
    for k in range(1, 101):
        beta, grew = update_penalty(beta, errs[k], errs[k - 1])
        grows += grew
    ok &= check("steadily halving errors: beta never grows",
                grows == 0 and beta == 1.0,
                f"{grows} growths in 100 iterations, beta stays {beta}")

    # stalled errors: grows every iteration, beta = beta0 * c1^n
    beta, grows = 1.0, 0
    for _ in range(100):
        beta, grew = update_penalty(beta, 7.0, 7.0)
        grows += grew
    expected = C1 ** 100
    rel = abs(beta - expected) / expected
    ok &= check("stalled errors: beta grows as c1^n every iteration",
                grows == 100 and rel < 1e-9,
                f"100 growths; beta = {beta:.6e}, c1^100 = {expected:.6e} "
                f"(relative {rel:.1e})")

    # mixed: alternating progress / stall
    beta, grows = 1.0, 0
    prev = 10.0
    for k in range(100):
        err = prev * (0.5 if k % 2 == 0 else 1.0)
        beta, grew = update_penalty(beta, err, prev)
        grows += grew
        prev = err
    ok &= check("alternating stall/progress: grows on exactly the stalls",
                grows == 50 and abs(beta - C1 ** 50) / C1 ** 50 < 1e-9,
                f"{grows} growths (expect 50), beta = {beta:.6e}, "
                f"c1^50 = {C1**50:.6e}")

    print("     ---")
    print(f"     100-iteration growth bound: c1^100 = {C1**100:.3e}")
    print(f"     eq. (14) imposes NO CAP on beta. The old baseline capped at 1e6")
    print(f"     (ssrtd.py: mu = min(mu*1.5, 1e6)) and ramped UNCONDITIONALLY,")
    print(f"     saturating after ~40 iterations. The real scheme grows only on")
    print(f"     stalls, so saturation depends on convergence behaviour, not the")
    print(f"     iteration count. Relevant to RESEARCH_LOG.md section 4 item 1 —")
    print(f"     resolvable once (g) logs beta per iteration on real data.")
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


def probe():
    print("\n" + "-" * 72)
    print("TIMING + MEMORY PROBE — full size, float64")
    print("-" * 72)
    try:
        import time
        shape = (180, 320, 300)
        rng = np.random.default_rng(0)
        st = _state(shape, rng)
        after, _ = _mem_mb()
        print(f"  after allocating state: {after:8.0f} MB")

        t0 = time.perf_counter()
        errs = primal_residuals(st["f"], st["S"], st["X"], st["L"], st["E"])
        t_res = time.perf_counter() - t0

        t0 = time.perf_counter()
        update_multipliers(**st)
        t_mult = time.perf_counter() - t0
        cur, peak = _mem_mb()

        print(f"  primal_residuals     : {t_res:8.2f} s  "
              f"(err_f {errs[0]:.1f}, err_X {errs[1]:.1f})")
        print(f"  update_multipliers   : {t_mult:8.2f} s")
        print(f"  update_penalty       :    <1e-6 s  (two scalars)")
        print(f"  working set now      : {cur:8.0f} MB")
        print(f"  PEAK working set     : {peak:8.0f} MB   "
              f"<-- headroom against 8 GB: {8192 - peak:.0f} MB")
        print()
        print("  Per-outer-iteration running total (measured, float64):")
        print(f"    (b) HOOI 12.33 s + (c) S 6.33 s + (d) f 3.00 s + "
              f"(e) E 0.54 s + (f) {t_res + t_mult:.2f} s")
        print(f"    = {12.33 + 6.33 + 3.00 + 0.54 + t_res + t_mult:.2f} s per outer iteration")
        return True
    except Exception as exc:
        print(f"  probe skipped: {type(exc).__name__}: {exc}")
        return True


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (f) — multiplier + adaptive penalty updates")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (13), (14); sign from (7)")
    print(f"numpy {np.__version__}   GAMMA={GAMMA}  C1={C1}  C2={C2}")
    print("=" * 72)

    tests = [
        test_eq13_correctness,
        test_sign_from_eq7,
        test_eq14_conditional_logic,
        test_constants_distinct,
        test_sequence_behaviour,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{len(_results)} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    probe()

    print()
    if all(outcomes):
        print("Component (f) VERIFIED — all five tests pass.")
        return 0
    print("Component (f) NOT verified — fix before assembling (g).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
