"""
Attribution probe for the Candela gate re-run of 2026-09-19 (RESEARCH_LOG.md section 6.6).

The re-run at 85f7eaf matched the a796ae6 gate to printed precision through
iteration ~30 and then diverged (err_X 3.5% apart at iteration 100), while every
criterion still passed. The only solver change since a796ae6 that is not bitwise
is the half-spectrum S-update (rfftn/irfftn, commit 463de7e; agreement with the
full-spectrum path is ~1e-16 per call, not 0). This probe runs the gate's exact
factor-2.0 solve at HEAD with the S-update forced back onto the RETAINED
full-spectrum path (update_S(..., half_spectrum=False), full Phi). If that history
matches a796ae6 to printed precision again, the divergence is the rfftn rounding
amplified by the iteration, and nothing else.

Writes results/scratch/probe_gate_fullspectrum/history_factor2_fullspectrum.csv.

    python -u -m src.probe_gate_fullspectrum
"""

import io
import time
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

from src import gate_candela as gate
from src import ssrtd_real as sr

PROJECT_DIR = Path(__file__).parent.parent
OUT_DIR = PROJECT_DIR / "results" / "scratch" / "probe_gate_fullspectrum"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with redirect_stdout(io.StringIO()):
        source, gt_path = gate.find_inputs(str(gate.DEFAULT_FRAMES_DIR), None)
        X_clean, _names, digest = gate.load_frames(source, gate.PAPER_N_FRAMES)
        L_true = gate.load_ground_truth(gt_path, X_clean.shape[2])
    X_noisy, _mask = gate.add_impulse_noise(X_clean, gate.PAPER_NOISE_RATIO, 0)

    # Force the retained full-spectrum route: ignore the half Phi the loop
    # precomputes and let update_S build the full Phi (once, cached here).
    phi_full = sr.compute_phi(X_noisy.shape)
    orig_update_S = sr.update_S

    def update_S_full(*args, **kwargs):
        kwargs["phi"] = phi_full
        kwargs["half_spectrum"] = False
        return orig_update_S(*args, **kwargs)

    sr.update_S = update_S_full
    print(f"probe_gate_fullspectrum  started {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  input sha256 {digest[:16]}...  factor 2.0  lambda {gate.PAPER_LAMBDA}  "
          f"S-update: full spectrum (fftn/ifftn)")
    t0 = time.perf_counter()
    r = sr.ssrtd_real(X_noisy, lam=gate.PAPER_LAMBDA, factor=2.0, max_iter=100, tol=1e-6,
                      log=True, verbose=True, L_true=L_true)
    wall = time.perf_counter() - t0
    hist = pd.DataFrame(r["history"])
    hist.to_csv(OUT_DIR / "history_factor2_fullspectrum.csv", index=False)

    ref = pd.read_csv(PROJECT_DIR / "results" / "gate_candela" / "history_factor2.csv")
    for col in ("err_X", "relChg_L", "relChg_S", "relErr_L", "beta_X"):
        a, b = hist[col].to_numpy(), ref[col].to_numpy()
        ok = np.isfinite(a) & np.isfinite(b)
        rel = np.abs(a[ok] - b[ok]) / np.maximum(np.abs(b[ok]), 1e-300)
        print(f"  {col:9s} vs a796ae6: max rel diff {rel.max():.2e} "
              f"(iter {int(hist['iter'].to_numpy()[ok][rel.argmax()])}); bitwise {np.array_equal(a, b)}")
    print(f"  wall {wall/60:.1f} min\nfinished {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
