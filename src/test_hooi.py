"""
Unit tests for Phase 1 component (b): Tucker / HOOI low-rank solver for L.

Covers src/ssrtd_real.py -- tucker_ranks, hosvd_init, hooi, tucker_core,
tucker_reconstruct -- against paper/SOURCE.md eq. (3) and (8).

Five tests plus a timing probe:
  1. exact recovery      synthetic Tucker tensor recovered to ~0 error
  2. rank-1 in time      r3=1 => mode-3 unfolding has sigma2/sigma1 ~ 0
  3. monotone decrease   HOOI objective non-increasing over the 20 iterations
  4. orthogonality       Uk^T Uk == I at every iteration (eq. 8 constraint)
  5. shapes and ranks    tucker_ranks((180,320,300)) == (144,256,1); G, L shapes

  timing probe           one real VIRAT tensor, literal paper settings.
                         Reported, not pass/fail -- it decides whether the
                         Phase 3 run is feasible as specified.

Note on test 2: IMPLEMENTATION_PLAN.md originally said this test should confirm
"every temporal slice of L identical". That is not the correct invariant. With
r3 = 1 the mode-3 unfolding is rank 1, so frame_t = u3[t] * (one common image):
frames are scalar MULTIPLES of each other, identical only if u3 is constant.
Asserting literal identity would fail on correct code. This test asserts the
real invariant (numerical rank 1) and reports the frame spread separately.

Run from the project directory as a module:
    python -m src.test_hooi
"""

import sys
import time

import numpy as np

from src.ssrtd_real import (
    tucker_ranks, feasible_ranks, mode_dot, hosvd_init, hooi, tucker_core,
    tucker_reconstruct,
)
from src.tensor_rpca import unfold

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def _random_orthonormal(n, r, rng):
    Q, _ = np.linalg.qr(rng.standard_normal((n, r)))
    return Q[:, :r]


def _synthetic_tucker(shape, ranks, rng):
    """Build an exactly-(ranks)-Tucker tensor and return it with its factors."""
    Us = [_random_orthonormal(shape[k], ranks[k], rng) for k in range(3)]
    G = rng.standard_normal(ranks)
    return tucker_reconstruct(G, Us), G, Us


# ---------------------------------------------------------------- test 1
def test_exact_recovery():
    """A tensor that IS exactly (r1,r2,r3)-Tucker must be recovered to ~0 error."""
    print("\n1. Exact recovery of a synthetic Tucker tensor")
    rng = np.random.default_rng(0)
    ok = True
    for shape, ranks in (((12, 10, 8), (4, 3, 2)),
                         ((9, 7, 11), (3, 3, 1)),
                         ((6, 6, 6), (2, 2, 2)),
                         ((9, 7, 11), (3, 5, 1))):   # over-specified on purpose
        X, _, _ = _synthetic_tucker(shape, ranks, rng)
        G, Us, L = hooi(X, ranks, n_iter=20)

        eff = feasible_ranks(shape, ranks)
        rel = float(np.linalg.norm(X - L) / np.linalg.norm(X))
        shapes_ok = (G.shape == eff) and (L.shape == X.shape)
        note = "" if eff == ranks else f"  [requested {ranks} -> attainable {eff}]"
        ok &= check(
            f"shape {shape}, ranks {ranks}",
            rel < 1e-10 and shapes_ok,
            f"relative reconstruction error = {rel:.3e}  "
            f"(G {G.shape}, L {L.shape}){note}",
        )
    return ok


# ---------------------------------------------------------------- test 2
def test_rank_one_in_time():
    """r3 = 1 => mode-3 unfolding of L is numerically rank 1 (frames proportional)."""
    print("\n2. r3 = 1 gives a rank-1 temporal mode (frames proportional)")
    rng = np.random.default_rng(1)
    ok = True
    for shape in ((16, 20, 10), (12, 14, 25)):
        # static background + moving blob + noise: realistic, not exactly low-rank
        base = rng.standard_normal((shape[0], shape[1], 1))
        X = np.repeat(base, shape[2], axis=2)
        X[3:6, 4:8, :] += rng.standard_normal((3, 4, shape[2]))
        X += 0.05 * rng.standard_normal(shape)

        ranks = tucker_ranks(shape)
        _, _, L = hooi(X, ranks, n_iter=20)

        s = np.linalg.svd(unfold(L, 2), compute_uv=False)
        ratio = float(s[1] / s[0]) if len(s) > 1 else 0.0

        # frames are proportional: report how far from literally identical
        frames = np.moveaxis(L, 2, 0).reshape(shape[2], -1)
        spread = float(np.abs(frames - frames[0]).max() / np.abs(frames).max())

        ok &= check(
            f"shape {shape}, ranks {ranks}",
            ratio < 1e-10,
            f"sigma2/sigma1 = {ratio:.3e} (rank-1 confirmed); "
            f"max frame deviation from frame 0 = {spread:.3e} "
            f"({'~identical' if spread < 1e-6 else 'proportional, not identical'})",
        )
    return ok


# ---------------------------------------------------------------- test 3
def test_monotone_decrease():
    """The paper states HOOI's objective is monotonically non-increasing."""
    print("\n3. Monotone decrease of the eq. (8) objective")
    rng = np.random.default_rng(2)
    ok = True
    for shape, ranks in (((14, 11, 9), (5, 4, 2)), ((16, 20, 10), None)):
        X = rng.standard_normal(shape)
        if ranks is None:
            ranks = tucker_ranks(shape)
        G, Us, L, hist = hooi(X, ranks, n_iter=20, return_history=True)

        errs = np.array([h["error"] for h in hist])
        # allow only round-off scale increases
        rises = np.diff(errs)
        worst_rise = float(rises.max()) if len(rises) else 0.0
        tol = 1e-9 * max(errs[0], 1.0)
        monotone = worst_rise <= tol

        # the cheap identity used for history must match the direct residual
        direct = float(np.linalg.norm(X - L))
        identity_gap = abs(direct - errs[-1]) / max(direct, 1.0)

        ok &= check(
            f"shape {shape}, ranks {ranks}",
            monotone and identity_gap < 1e-8,
            f"error {errs[0]:.6f} -> {errs[-1]:.6f}, worst rise {worst_rise:+.2e} "
            f"(tol {tol:.1e}); ||X-L|| identity gap {identity_gap:.2e}",
        )
    return ok


# ---------------------------------------------------------------- test 4
def test_orthogonality():
    """eq. (8) constrains Uj^T Uj = I; check it holds at every iteration."""
    print("\n4. Factor orthogonality Uk^T Uk == I at every iteration")
    rng = np.random.default_rng(3)
    ok = True
    for shape, ranks in (((14, 11, 9), (5, 4, 2)), ((16, 20, 10), None)):
        X = rng.standard_normal(shape)
        if ranks is None:
            ranks = tucker_ranks(shape)
        _, Us, _, hist = hooi(X, ranks, n_iter=20, return_history=True)

        eff = feasible_ranks(shape, ranks)
        worst_iter = max(h["max_orth_err"] for h in hist)
        worst_final = max(
            float(np.abs(U.T @ U - np.eye(U.shape[1])).max()) for U in Us
        )
        shapes_ok = all(Us[k].shape == (shape[k], eff[k]) for k in range(3))

        ok &= check(
            f"shape {shape}, ranks {ranks}",
            worst_iter < 1e-12 and worst_final < 1e-12 and shapes_ok,
            f"max|Uk^T Uk - I| over 20 iterations = {worst_iter:.2e}, "
            f"final = {worst_final:.2e}, factor shapes ok = {shapes_ok}",
        )
    return ok


# ---------------------------------------------------------------- test 5
def test_shapes_and_ranks():
    """The paper's rank rule: r1 = ceil(0.8H), r2 = ceil(0.8W), r3 = 1."""
    print("\n5. Rank rule and shapes")
    ok = True

    got = tucker_ranks((180, 320, 300))
    ok &= check(
        "tucker_ranks((180,320,300)) == (144, 256, 1)",
        got == (144, 256, 1),
        f"got {got}  [ceil(0.8*180)=144, ceil(0.8*320)=256, r3 fixed at 1]",
    )

    cases = [((100, 100, 50), (80, 80, 1)),
             ((7, 13, 4), (6, 11, 1)),        # ceil(5.6)=6, ceil(10.4)=11
             ((5, 5, 1), (4, 4, 1))]
    for shape, expected in cases:
        got = tucker_ranks(shape)
        ok &= check(f"tucker_ranks({shape})", got == expected, f"got {got}, expected {expected}")

    # ranks never exceed their dimension (float-repr guard)
    bad = [s for s in [(1, 1, 1), (2, 3, 5), (10, 10, 10)]
           if any(tucker_ranks(s)[k] > s[k] for k in range(3))]
    ok &= check("ranks never exceed dimensions", not bad, f"violations: {bad}")

    # --- rank feasibility: r_k <= prod_{j!=k} r_j; with r3=1 this forces r1==r2
    got = feasible_ranks((180, 320, 300), (144, 256, 1))
    ok &= check(
        "paper's ranks (144,256,1) are NOT attainable -> (144,144,1)",
        got == (144, 144, 1),
        f"got {got}. With r3=1 every frame of L is a multiple of one HxW image, "
        f"whose rank is at most min(r1,r2), so r2=256 is unreachable.",
    )
    got = feasible_ranks((288, 352, 80), tucker_ranks((288, 352, 80)))
    ok &= check(
        "same on the paper's own Candela shape (288x352x80)",
        got == (231, 231, 1),
        f"tucker_ranks -> {tucker_ranks((288, 352, 80))}, attainable -> {got}",
    )
    for shape, req, exp in (((16, 20, 10), (13, 16, 1), (13, 13, 1)),
                            ((12, 10, 8), (4, 3, 2), (4, 3, 2)),
                            ((9, 7, 11), (3, 5, 1), (3, 3, 1))):
        got = feasible_ranks(shape, req)
        ok &= check(f"feasible_ranks({shape}, {req})", got == exp, f"got {got}, expected {exp}")

    # G and L shapes from a real call
    rng = np.random.default_rng(4)
    shape, ranks = (11, 9, 7), (4, 3, 2)
    X = rng.standard_normal(shape)
    G, Us, L = hooi(X, ranks, n_iter=5)
    ok &= check(
        "G and L shapes",
        G.shape == ranks and L.shape == shape,
        f"G {G.shape} (expect {ranks}), L {L.shape} (expect {shape})",
    )

    # mode_dot round-trip against an explicit reconstruction
    L2 = tucker_reconstruct(tucker_core(X, Us), Us)
    ok &= check(
        "tucker_core / tucker_reconstruct consistency",
        float(np.abs(L - L2).max()) < 1e-12,
        f"max|L - reconstruct(core(X))| = {float(np.abs(L - L2).max()):.2e}",
    )
    return ok


# ---------------------------------------------------------------- timing probe
def timing_probe():
    """
    Literal paper settings on one real VIRAT tensor. Reported, not asserted.

    Establishes whether 100 outer ADMM iterations x 20 inner HOOI iterations
    x 180 videos is feasible without warm-starting.
    """
    print("\n" + "-" * 72)
    print("TIMING PROBE — literal paper settings, one real VIRAT tensor")
    print("-" * 72)
    try:
        from src.preprocessing import load_video_frames, frames_to_tensor, load_registry
        from src.ssrtd_real import __file__ as _f  # noqa: F401
        from pathlib import Path

        PROJECT_DIR = Path(__file__).parent.parent
        df = load_registry(PROJECT_DIR / "video_registry.csv")
        first = df.iloc[0]
        path = PROJECT_DIR / "data" / "videos" / first["original_filename"]

        t0 = time.perf_counter()
        frames = load_video_frames(path, max_frames=300)
        X = frames_to_tensor(frames)
        t_load = time.perf_counter() - t0

        ranks = tucker_ranks(X.shape)
        print(f"  video   : {first['short_id']} ({first['original_filename']})")
        print(f"  tensor  : {X.shape}  ({X.size:,} elements)  load {t_load:.1f}s")
        print(f"  ranks   : {ranks}")

        t0 = time.perf_counter()
        hosvd_init(X, ranks)
        t_init = time.perf_counter() - t0
        print(f"  HOSVD init          : {t_init:8.2f} s")

        t0 = time.perf_counter()
        _, _, L = hooi(X, ranks, n_iter=20)
        t_hooi = time.perf_counter() - t0

        rel = float(np.linalg.norm(X - L) / np.linalg.norm(X))
        per_iter = t_hooi / 20
        print(f"  HOOI, 20 iterations : {t_hooi:8.2f} s   ({per_iter:.2f} s/iter)")
        print(f"  relative error      : {rel:.4f}")
        print()
        print("  Projection to the full Phase 3 run (literal, no warm-starting):")
        outer = 100
        per_video = t_hooi * outer
        print(f"    per video, {outer} outer x 20 inner : {per_video/60:8.1f} min")
        print(f"    180 videos                       : {per_video*180/3600:8.1f} h")
        print("  (upper bound: many runs stop before 100 outer iterations)")
        return True
    except Exception as exc:                      # probe must never fail the suite
        print(f"  probe skipped: {type(exc).__name__}: {exc}")
        return True


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (b) — Tucker / HOOI low-rank solver for L")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md eq. (3), (8)")
    print(f"numpy {np.__version__}")
    print("=" * 72)

    tests = [
        test_exact_recovery,
        test_rank_one_in_time,
        test_monotone_decrease,
        test_orthogonality,
        test_shapes_and_ranks,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{len(_results)} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    timing_probe()

    print()
    if all(outcomes):
        print("Component (b) VERIFIED — all five tests pass.")
        return 0
    print("Component (b) NOT verified — fix before moving to (c).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
