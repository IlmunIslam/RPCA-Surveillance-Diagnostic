"""
Unit tests for Phase 1 component (g1): the full ADMM assembly.

Covers src/ssrtd_real.py -- ssrtd_real -- against paper/SOURCE.md Algorithm 1.

Six tests:
  1. initialization       L from Tucker of X (not X_tilde); S = X - L;
                          E, Lambda_X, lambda_f, f all EXACTLY zero; beta values
  2. reconstruction       the constraint residual ||X - L - S - E||_F shrinks
  3. convergence/stopping n_iter, converged and history are truthful; the
                          max_iter cap holds; the degenerate first-iteration
                          stop is not mistaken for convergence
  4. synthetic recovery   the three components land in the RIGHT SOCKETS:
                          L rank-1 in time, E sparse, S smooth relative to E
  5. determinism/params   identical inputs give identical outputs; lambda and
                          factor behave as parameters
  6. logging completeness every field promised by the Output Contract is
                          present, finite and per-iteration

All tests use small tensors. No full-size or VIRAT run happens here -- that is
gated on (g2), the Candela verification gate.

Test 4 is the one that checks the six components were wired to the right
sockets. Every other test would pass with L and S swapped.

Run from the project directory as a module:
    python -m src.test_ssrtd_real
"""

import sys

import numpy as np

from src.ssrtd_real import (
    E_THRESHOLD_FACTOR, compute_phi, hooi, ssrtd_real, tucker_ranks, tv_norm,
)
from src.tensor_rpca import unfold

_results = []


def check(name, passed, detail=""):
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return passed


def synthetic(shape=(12, 14, 8), noise_ratio=0.10, seed=0):
    """Static background + smooth moving blob + random-valued impulse noise."""
    rng = np.random.default_rng(seed)
    H, W, T = shape
    L = np.repeat(rng.uniform(0.2, 0.8, (H, W, 1)), T, axis=2)
    S = np.zeros(shape)
    for t in range(T):                      # a blob drifting down the frame
        c = 2 + int(6 * t / T)
        S[c:c + 3, 4:8, t] = 0.5
    E = np.zeros(shape)
    mask = rng.random(shape) < noise_ratio
    E[mask] = rng.uniform(-1, 1, int(mask.sum()))
    return L + S + E, L, S, E


# ---------------------------------------------------------------- test 1
def test_initialization():
    """Algorithm 1's initialization, exactly as printed."""
    print("\n1. Initialization — Algorithm 1 as printed")
    ok = True
    for shape, seed in (((12, 14, 8), 0), ((9, 11, 6), 1)):
        X, _, _, _ = synthetic(shape, seed=seed)
        r = ssrtd_real(X, lam=0.4, max_iter=0)      # no iterations: initial state

        ranks = tucker_ranks(shape)
        _, _, L_expected = hooi(X, ranks, n_iter=20)   # Tucker of X, not X_tilde

        L_ok = float(np.abs(r["L"] - L_expected).max()) <= 1e-12
        S_ok = float(np.abs(r["S"] - (X - r["L"])).max()) == 0.0
        zeros_ok = all(float(np.abs(r[k]).max()) == 0.0
                       for k in ("E", "mult_X", "mult_f", "f"))
        mean_X = float(np.mean(X))
        beta_ok = (abs(r["beta_f"] - 1e+1 / mean_X) <= 1e-12
                   and abs(r["beta_X"] - 4e-1 / mean_X) <= 1e-12)
        loop_ok = r["n_iter"] == 0 and r["history"] == [] and not r["converged"]

        ok &= check(
            f"shape {shape}",
            L_ok and S_ok and zeros_ok and beta_ok and loop_ok,
            f"L from Tucker of X ({L_ok}); S = X - L exactly ({S_ok}); "
            f"E/Lambda_X/lambda_f/f all exactly 0 ({zeros_ok}); "
            f"beta_f={r['beta_f']:.4f}=1e+1/mean(X), "
            f"beta_X={r['beta_X']:.4f}=4e-1/mean(X) ({beta_ok})",
        )

    # f = 0, NOT D vec(S) -- the counter-intuitive one
    X, _, _, _ = synthetic()
    r = ssrtd_real(X, lam=0.4, max_iter=0)
    from src.ssrtd_real import tv_forward
    dvs = tv_forward(r["S"])
    ok &= check(
        "f initialized to 0, not to D vec(S)",
        float(np.abs(r["f"]).max()) == 0.0 and float(np.abs(dvs).max()) > 1e-6,
        f"max|f| = {float(np.abs(r['f']).max()):.1e} (must be 0); "
        f"max|D vec(S)| = {float(np.abs(dvs).max()):.4f} (nonzero, so the two "
        f"initializations are genuinely different)",
    )
    return ok


# ---------------------------------------------------------------- test 2
def test_reconstruction():
    """The constraint residual ||X - L - S - E||_F must shrink."""
    print("\n2. Reconstruction — the eq. (6) constraint residual shrinks")
    ok = True
    for seed in (0, 1, 2):
        X, _, _, _ = synthetic(seed=seed)
        r = ssrtd_real(X, lam=0.4, max_iter=60)
        errs = [h["err_X"] for h in r["history"]]

        final = float(np.linalg.norm((X - r["L"] - r["S"] - r["E"]).ravel()))
        rel = final / float(np.linalg.norm(X.ravel()))
        shrank = errs[-1] < errs[0]
        agrees = abs(final - errs[-1]) <= 1e-9

        ok &= check(
            f"seed {seed}",
            shrank and rel < 0.10 and agrees,
            f"err_X {errs[0]:.3f} -> {errs[-1]:.3f}; final residual "
            f"{final:.4f} = {rel*100:.2f}% of ||X|| ; history agrees ({agrees})",
        )
    return ok


# ---------------------------------------------------------------- test 3
def test_convergence_and_stopping():
    """n_iter, converged and history must be truthful, and the cap must hold."""
    print("\n3. Convergence and stopping")
    ok = True
    X, _, _, _ = synthetic(seed=1)

    # (a) impossible tolerance -> runs to the cap, reports not converged
    r = ssrtd_real(X, lam=0.4, max_iter=12, tol=1e-30)
    ok &= check(
        "impossible tol runs to max_iter and reports converged=False",
        r["n_iter"] == 12 and not r["converged"] and len(r["history"]) == 12,
        f"n_iter={r['n_iter']} (cap 12), converged={r['converged']}, "
        f"history length {len(r['history'])}",
    )

    # (b) loose tolerance -> stops early and reports converged=True
    r = ssrtd_real(X, lam=0.4, max_iter=80, tol=0.1)
    stopped_early = r["n_iter"] < 80
    last = r["history"][-1]["relChg_E"]
    ok &= check(
        "loose tol converges early and the final relChg_E is below it",
        stopped_early and r["converged"] and last <= 0.1
        and len(r["history"]) == r["n_iter"],
        f"n_iter={r['n_iter']} of 80, converged={r['converged']}, "
        f"final relChg_E={last:.4e} <= tol 0.1",
    )

    # (c) the degenerate first-iteration stop must NOT count as convergence
    r = ssrtd_real(X, lam=0.4, max_iter=25, tol=1e-6)
    first_E_zero = r["history"][0]["relChg_E"] == float("inf")
    ok &= check(
        "degenerate zero-E start is not mistaken for convergence",
        r["n_iter"] > 1 and first_E_zero,
        f"n_iter={r['n_iter']} (literal Algorithm 1 would stop at 1, because "
        f"E_0 = E_1 = 0 gives relChg = 0 <= tol); iteration 1 relChg_E reported "
        f"as inf while E is identically zero",
    )

    # (d) history length always equals n_iter
    lengths_ok = True
    for mx in (1, 3, 7):
        rr = ssrtd_real(X, lam=0.4, max_iter=mx, tol=1e-30)
        lengths_ok &= (len(rr["history"]) == rr["n_iter"] == mx
                       and [h["iter"] for h in rr["history"]] == list(range(1, mx + 1)))
    ok &= check("history length and iter numbering match n_iter", lengths_ok,
                "checked at max_iter = 1, 3, 7")
    return ok


# ---------------------------------------------------------------- test 4
def test_synthetic_recovery():
    """
    The six components must be wired to the RIGHT SOCKETS.

    Structural properties, each specific to one slot:
      L  -- rank 1 in the temporal mode (r3 = 1)
      E  -- sparse (a soft-threshold output)
      S  -- smooth relative to E, measured as TV per unit l1 mass

    Every other test in this file would pass with L and S swapped. This one
    would not.
    """
    print("\n4. Synthetic recovery — components in the right sockets")
    ok = True
    for seed in (0, 1, 2):
        X, L_true, S_true, E_true = synthetic(seed=seed)
        r = ssrtd_real(X, lam=0.4, max_iter=60)
        L, S, E = r["L"], r["S"], r["E"]

        sv = np.linalg.svd(unfold(L, 2), compute_uv=False)
        l_rank1 = float(sv[1] / sv[0]) < 1e-10

        e_sparse = float(np.mean(E == 0.0)) > 0.5

        tv_S = tv_norm(S) / max(float(np.abs(S).sum()), 1e-12)
        tv_E = tv_norm(E) / max(float(np.abs(E).sum()), 1e-12)
        s_smoother = tv_S < tv_E / 2.0

        recon = float(np.linalg.norm((X - L - S - E).ravel())
                      / np.linalg.norm(X.ravel()))

        # reported, not asserted: L and S share a static component, so the
        # split between them is not unique and relErr_L is not a stable quantity
        rel_L = float(np.linalg.norm((L - L_true).ravel())
                      / np.linalg.norm(L_true.ravel()))

        ok &= check(
            f"seed {seed}",
            l_rank1 and e_sparse and s_smoother and recon < 0.10,
            f"L sigma2/sigma1 = {sv[1]/sv[0]:.1e} (rank-1); E zeros "
            f"{100*np.mean(E == 0):.0f}%; TV per unit l1: S {tv_S:.2f} vs "
            f"E {tv_E:.2f} (S smoother by {tv_E/max(tv_S,1e-12):.1f}x); "
            f"reconstruction {recon*100:.2f}% of ||X||  "
            f"[relErr_L {rel_L:.2f}, reported only]",
        )

    print("     ---")
    print("     relErr_L is deliberately NOT asserted: L and S both contain a")
    print("     static component, so their split is not unique and relErr_L")
    print("     ranged 0.15-1.06 across seeds. Asserting it would be brittle and")
    print("     would test the synthetic construction, not the implementation.")
    return ok


# ---------------------------------------------------------------- test 5
def test_determinism_and_parameters():
    """Reproducibility, plus lambda and factor behaving as parameters."""
    print("\n5. Determinism and parameter behaviour")
    ok = True
    X, _, _, _ = synthetic(seed=2)

    a = ssrtd_real(X, lam=0.4, max_iter=20)
    b = ssrtd_real(X, lam=0.4, max_iter=20)
    identical = all(np.array_equal(a[k], b[k]) for k in ("L", "S", "E", "f"))
    ok &= check("identical inputs give bitwise identical outputs", identical,
                "no RNG anywhere in the solver; required for the Phase 3 "
                "reproducibility claim")

    # larger lambda penalizes TV harder -> smoother S
    tvs = []
    for lam in (0.2, 0.5, 1.0):
        r = ssrtd_real(X, lam=lam, max_iter=25)
        tvs.append(tv_norm(r["S"]) / max(float(np.abs(r["S"]).sum()), 1e-12))
    ok &= check(
        "larger lambda gives a smoother S (TV per unit l1 mass)",
        tvs[-1] <= tvs[0],
        f"lambda 0.2 -> 1.0: TV/l1 = {tvs[0]:.3f}, {tvs[1]:.3f}, {tvs[2]:.3f}",
    )

    # both E-threshold factors run and differ
    r2 = ssrtd_real(X, lam=0.4, max_iter=20, factor=2.0)
    r1 = ssrtd_real(X, lam=0.4, max_iter=20, factor=1.0)
    differ = float(np.abs(r2["E"] - r1["E"]).max()) > 1e-9
    ok &= check(
        "factor 1.0 and 2.0 both run and give different E",
        differ and r2["factor"] == 2.0 and r1["factor"] == 1.0,
        f"E zeros: factor 2.0 -> {100*np.mean(r2['E'] == 0):.0f}%, "
        f"factor 1.0 -> {100*np.mean(r1['E'] == 0):.0f}%; "
        f"max|E2 - E1| = {float(np.abs(r2['E'] - r1['E']).max()):.4f}  "
        f"[the (g) carry-forward decision]",
    )

    # warm_start runs and is off by default
    rw = ssrtd_real(X, lam=0.4, max_iter=20, warm_start=True)
    ok &= check(
        "warm_start=True runs (deviation, off by default)",
        rw["n_iter"] == 20 and np.isfinite(rw["history"][-1]["err_X"]),
        f"final err_X {rw['history'][-1]['err_X']:.4f} vs literal "
        f"{a['history'][-1]['err_X']:.4f} — comparison deferred to (g2)",
    )

    # default factor is the printed one
    ok &= check("default factor is eq. (12)'s printed 2.0",
                ssrtd_real(X, lam=0.4, max_iter=1)["factor"] == E_THRESHOLD_FACTOR
                == 2.0,
                "the literal paper value, not the Appendix A one")
    return ok


# ---------------------------------------------------------------- test 6
def test_logging_completeness():
    """Every field the Output Contract promises, present and finite."""
    print("\n6. Logging completeness — the Output Contract")
    ok = True
    X, L_true, _, _ = synthetic(seed=0)
    r = ssrtd_real(X, lam=0.4, max_iter=15, L_true=L_true)

    required = ["iter", "relChg_L", "relChg_S", "relChg_E", "relErr_L",
                "err_f", "err_X", "beta_f", "beta_X", "beta_f_grew",
                "beta_X_grew", "obj_E_l1", "obj_S_tv1", "seconds"]
    missing = [k for k in required if k not in r["history"][0]]
    ok &= check("all promised fields present", not missing,
                f"{len(required)} fields: {', '.join(required)}"
                + (f"  MISSING: {missing}" if missing else ""))

    numeric = [k for k in required if k not in ("beta_f_grew", "beta_X_grew")]
    # relChg_E is inf on iterations where E is identically zero, by design
    bad = [(h["iter"], k) for h in r["history"] for k in numeric
           if not np.isfinite(h[k]) and not (k == "relChg_E" and np.isinf(h[k]))]
    ok &= check("all numeric fields finite (bar the documented inf)", not bad,
                f"checked {len(r['history'])} iterations x {len(numeric)} fields"
                + (f"  BAD: {bad[:5]}" if bad else ""))

    ok &= check("relErr_L populated when L_true is supplied",
                all(np.isfinite(h["relErr_L"]) for h in r["history"]),
                f"relErr_L {r['history'][0]['relErr_L']:.4f} -> "
                f"{r['history'][-1]['relErr_L']:.4f} (needed for the (g2) "
                f"Fig. 3 reproduction)")

    r2 = ssrtd_real(X, lam=0.4, max_iter=3)
    ok &= check("relErr_L is nan when no ground truth is given",
                all(np.isnan(h["relErr_L"]) for h in r2["history"]),
                "nan rather than a silent zero")

    ok &= check("beta growth flags are booleans",
                all(isinstance(h["beta_f_grew"], bool)
                    and isinstance(h["beta_X_grew"], bool) for h in r["history"]),
                f"beta_X grew on "
                f"{sum(h['beta_X_grew'] for h in r['history'])}/"
                f"{len(r['history'])} iterations — the data that answers "
                f"RESEARCH_LOG.md section 4 item 1")

    ok &= check("solver returns the full state",
                all(k in r for k in ("L", "S", "E", "G", "Us", "f", "mult_f",
                                     "mult_X", "beta_f", "beta_X", "ranks",
                                     "ranks_effective", "n_iter", "converged",
                                     "history", "lam", "factor")),
                f"ranks {r['ranks']} -> effective {r['ranks_effective']}")
    return ok


# ---------------------------------------------------------------- test 7
def test_bitwise_reference():
    """
    The memory levers (in-place thresholding, single tv_forward per iteration,
    affine adjoint, early *_prev release) change ALLOCATION, never arithmetic.
    So the solver must reproduce, BITWISE, the histories and final state
    recorded from the pre-lever solver at commit a131d7c on these synthetic
    tensors (src/testdata/ssrtd_real_reference_a131d7c.*). Any difference at
    all -- even in the last bit -- means a lever changed the numbers.
    """
    import json
    from pathlib import Path
    print("\n7. Bitwise reproduction of the pre-lever reference (commit a131d7c)")
    tdir = Path(__file__).parent / "testdata"
    ref = np.load(tdir / "ssrtd_real_reference_a131d7c.npz")
    meta = json.load(open(tdir / "ssrtd_real_reference_a131d7c.json"))["runs"]
    ok = True
    for key, m in meta.items():
        X = ref[f"{key}_X"]
        r = ssrtd_real(X, lam=m["lam"], max_iter=m["max_iter"], factor=m["factor"])

        cols = m["hist_cols"]
        hist = np.array([[h[c] for c in cols] for h in r["history"]], dtype=np.float64)
        grew = np.array([[h["beta_f_grew"], h["beta_X_grew"]] for h in r["history"]], dtype=bool)
        hist_ok = hist.shape == ref[f"{key}_hist"].shape and hist.tobytes() == ref[f"{key}_hist"].tobytes()
        grew_ok = np.array_equal(grew, ref[f"{key}_grew"])
        state_ok = all(r[k].tobytes() == ref[f"{key}_{k}"].tobytes()
                       for k in ("L", "S", "E", "f", "mult_f", "mult_X"))
        beta_ok = r["beta_f"] == m["beta_f"] and r["beta_X"] == m["beta_X"]
        meta_ok = r["n_iter"] == m["n_iter"] and r["converged"] == m["converged"]

        worst = max(float(np.abs(r[k] - ref[f"{key}_{k}"]).max())
                    for k in ("L", "S", "E", "f", "mult_f", "mult_X"))
        ok &= check(
            f"{key}: shape {tuple(m['shape'])}, lam {m['lam']}, {m['max_iter']} iterations",
            hist_ok and grew_ok and state_ok and beta_ok and meta_ok,
            f"history bitwise={hist_ok} ({hist.shape[0]}x{hist.shape[1]}), growth flags={grew_ok}, "
            f"final L/S/E/f/multipliers bitwise={state_ok} (max abs diff {worst:.1e}), "
            f"betas={beta_ok}, n_iter/converged={meta_ok}",
        )
    return ok


# ---------------------------------------------------------------- runner
def main():
    print("=" * 72)
    print("Phase 1 component (g1) — full ADMM assembly, Algorithm 1")
    print("src/ssrtd_real.py  vs  paper/SOURCE.md Algorithm 1")
    print(f"numpy {np.__version__}   (small tensors only; no VIRAT, no full-size)")
    print("=" * 72)

    tests = [
        test_initialization,
        test_reconstruction,
        test_convergence_and_stopping,
        test_synthetic_recovery,
        test_determinism_and_parameters,
        test_logging_completeness,
        test_bitwise_reference,
    ]
    outcomes = [t() for t in tests]

    n_pass = sum(1 for _, p, _ in _results if p)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {n_pass}/{len(_results)} assertions passed across {len(tests)} tests")
    for t, outcome in zip(tests, outcomes):
        print(f"  {'PASS' if outcome else 'FAIL'}  {t.__name__}")
    print("=" * 72)

    print()
    if all(outcomes):
        print("Component (g1) VERIFIED — all seven tests pass.")
        print("(g2) verification gate still REQUIRED before any VIRAT run.")
        return 0
    print("Component (g1) NOT verified.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
