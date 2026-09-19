"""
Probe for RESEARCH_LOG.md section 6.3: the relChg_L mid-run plateau on Candela.

Question: is the plateau (relChg_L ~ 0.010 over iterations 15-40, where the paper's
Fig. 3 shows ~0.002) sensitive to the one part of Algorithm 1 the paper leaves
unspecified -- how the HOOI inner solve is run at each outer iteration?

Runs real SS-RTD on the gate's exact input (Candela, first 80 frames, 10% impulse
noise, seed 0, lambda 0.4, factor 1.0, 100 iterations) under HOOI variants:

  baseline   hooi_iters=20, cold start          (Algorithm 1 as implemented; = gate)
  warm       hooi_iters=20, warm_start=True     (factors carried between outer iterations)
  converged  hooi_iters=100, cold start         (inner solve run much further)

Writes results/scratch/probe_relchg_L/history_<variant>.csv and summary.json.
These are NOT gate results and NOT Phase 3 results; the solver's Phase 3
configuration is unchanged by this probe.

    python -u -m src.probe_relchg_L --variants warm,converged
"""

import argparse
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

from src import gate_candela as gate
from src.ssrtd_real import ssrtd_real

PROJECT_DIR = Path(__file__).parent.parent
OUT_DIR = PROJECT_DIR / "results" / "scratch" / "probe_relchg_L"

VARIANTS = {
    "baseline": dict(hooi_iters=20, warm_start=False),
    "warm": dict(hooi_iters=20, warm_start=True),
    "converged": dict(hooi_iters=100, warm_start=False),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="warm,converged")
    ap.add_argument("--max-iter", type=int, default=100)
    args = ap.parse_args()
    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    for n in names:
        if n not in VARIANTS:
            sys.exit(f"unknown variant {n!r}; choose from {list(VARIANTS)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with redirect_stdout(io.StringIO()):
        source, gt_path = gate.find_inputs(str(gate.DEFAULT_FRAMES_DIR), None)
        X_clean, _names, digest = gate.load_frames(source, gate.PAPER_N_FRAMES)
        L_true = gate.load_ground_truth(gt_path, X_clean.shape[2])
    X_noisy, _mask = gate.add_impulse_noise(X_clean, gate.PAPER_NOISE_RATIO, 0)
    print(f"probe_relchg_L  started {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  input sha256 {digest[:16]}...  shape {X_noisy.shape}  variants {names}")

    summary = {"input_sha256": digest, "lam": gate.PAPER_LAMBDA, "factor": 1.0,
               "max_iter": args.max_iter, "variants": {}}
    for name in names:
        kw = VARIANTS[name]
        print(f"\n--- variant {name}: {kw} ---")
        t0 = time.perf_counter()
        r = ssrtd_real(X_noisy, lam=gate.PAPER_LAMBDA, factor=1.0, max_iter=args.max_iter,
                       tol=1e-6, log=True, verbose=True, L_true=L_true, **kw)
        wall = time.perf_counter() - t0
        hist = pd.DataFrame(r["history"])
        hist.insert(0, "variant", name)
        hist.to_csv(OUT_DIR / f"history_{name}.csv", index=False)
        rl = hist.set_index("iter")["relChg_L"]
        summary["variants"][name] = {
            **kw, "wall_min": round(wall / 60, 2), "n_iter": int(r["n_iter"]),
            "relChg_L_at": {str(i): float(rl.loc[i]) for i in (15, 20, 30, 40, 60, 80, 100) if i in rl.index},
            "relChg_L_plateau_15_40_median": float(rl.loc[15:40].median()),
            "final_relErr_L": float(hist["relErr_L"].iloc[-1]) if "relErr_L" in hist else None,
            "final_err_X": float(hist["err_X"].iloc[-1]),
        }
        print(f"  {name}: {wall/60:.1f} min; relChg_L median over 15-40 = "
              f"{summary['variants'][name]['relChg_L_plateau_15_40_median']:.4f}; "
              f"final err_X {summary['variants'][name]['final_err_X']:.2f}")
        with open(OUT_DIR / "summary.json", "w") as fh:
            json.dump(summary, fh, indent=2)
    print(f"\nfinished {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
