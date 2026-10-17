"""
Phase 3 worker: ONE real-SS-RTD run on ONE VIRAT video, in its own process.

One run = (video_id, condition, factor, lam, seed). The worker does the solve, the
metrics, the H.264 step and the per-run artifacts, and writes summary.json LAST --
its presence is what marks the run complete. The worker NEVER touches the results
CSV; only src/phase3_runner.py writes that (PHASE3_NOTES.md: never two writers).

Conditions (RESEARCH_LOG.md section 8):
  clean      the video as it is -- the realistic surveillance condition
  impulse10  the paper's noise model, 10% of pixels per frame replaced by uniform
             random integers in [0,255] (scaled to the [0,1] tensor), positions
             recorded so E's recall/precision can be measured

Run directly only for debugging; the runner is the normal entry point:
    python -m src.phase3_worker --video-id video_01 --condition clean
        --factor 1.0 --lam 0.4 --out-dir results/scratch/phase3_smoke/<run>
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from src.compression import encode_frames_h264
from src.gate_candela import add_impulse_noise
from src.metrics import (compute_foreground_density, compute_psnr_sequence,
                         compute_ssim_sequence, get_file_size_kb)
from src.preprocessing import frames_to_tensor, load_registry, load_video_frames
from src.ssrtd_real import feasible_ranks, ssrtd_real, tucker_ranks

PROJECT_DIR = Path(__file__).parent.parent

CONDITIONS = ("clean", "impulse10")
NOISE_RATIO = 0.10                    # the paper's 10%, fixed for condition impulse10
MAX_ITER = 100                        # Algorithm 1's cap; never reduced (rigor rule)
TOL = 1e-6
THRESHOLDS = (0.01, 0.05)             # the support cuts the finding is measured on
CRF_REF, CRF_COMP = 23, 28            # as in the baseline's compression step
FPS = 25.0

_FORBIDDEN = ("all_results", "param_sweep", "baseline_naive")


# Column-name suffix per threshold. An explicit map, not string surgery on the
# float: str(0.05).replace("0.", "") gives "05", which silently did NOT match the
# runner's S_gt005_pct column and wrote the 0.05 occupancies as empty cells. The
# runner's "fields not in COLUMNS" report caught it on the first smoke run; keep
# both this map and that report.
_TAGS = {0.01: "001", 0.05: "005"}


def _tag(t):
    """0.01 -> '001', 0.05 -> '005' -- the suffixes used in the CSV column names."""
    return _TAGS[t]


def to_frames(tensor):
    """(H, W, T) -> (T, H, W), the orientation the metric and encoder helpers take."""
    return np.transpose(tensor, (2, 0, 1))


def support_stats(A, name, thresholds=THRESHOLDS):
    """Occupancy of a component at each threshold, plus its exact-zero fraction."""
    out = {f"{name}_nonzero_pct": round(100.0 * float(np.mean(A != 0)), 4)}
    for t in thresholds:
        out[f"{name}_gt{_tag(t)}_pct"] = round(100.0 * float(np.mean(np.abs(A) > t)), 4)
    return out


def se_overlap(S, E, t=0.05):
    """
    Share of the pixels S claims (|S| > t) that E also claims (|E| > t).

    This is the number the smooth-vs-sharp finding rests on: if S and E are
    separating it is small; the first VIRAT look gave 45% (RESEARCH_LOG.md 7.4).
    """
    s_mask = np.abs(S) > t
    n = int(s_mask.sum())
    if n == 0:
        return {"SE_overlap_005": None, "S_claimed_px": 0, "SE_both_px": 0}
    both = int((s_mask & (np.abs(E) > t)).sum())
    return {"SE_overlap_005": round(100.0 * both / n, 4),
            "S_claimed_px": n, "SE_both_px": both}


def noise_recovery(E, mask, X_clean, X_noisy, thresholds=THRESHOLDS):
    """
    How well E recovers the injected impulses. `mask` is the ground-truth support.

    Two recalls are reported because they answer different questions:
      E_recall             over every corrupted position
      E_recall_detectable  over corrupted positions whose value actually changed
                           (a corruption that redraws the same integer is invisible
                           to any method -- about 1 in 256 of them)
    """
    out = {}
    detectable = mask & (X_noisy != X_clean)
    n_mask = max(int(mask.sum()), 1)
    n_det = max(int(detectable.sum()), 1)
    for t in thresholds:
        hit = np.abs(E) > t
        tp = int((hit & mask).sum())
        out[f"E_recall_{_tag(t)}"] = round(tp / n_mask, 6)
        out[f"E_precision_{_tag(t)}"] = round(tp / max(int(hit.sum()), 1), 6)
        out[f"E_recall_detectable_{_tag(t)}"] = round(int((hit & detectable).sum()) / n_det, 6)
    nz = E != 0
    out["E_recall"] = round(int((nz & mask).sum()) / n_mask, 6)
    out["E_precision"] = round(int((nz & mask).sum()) / max(int(nz.sum()), 1), 6)
    out["noise_detectable_pct"] = round(100.0 * int(detectable.sum()) / n_mask, 4)
    return out


def h264_sizes(X_input, L, S, E, work_dir):
    """
    File sizes of the input and of each component, encoded exactly as the baseline
    encoded them, so the numbers are comparable with the archived columns.

    The baseline mapped a tensor to video with (x*255).clip(0,255), which DISCARDS
    the negative half of a signed component. That mapping is kept (S_crf28_kb,
    E_crf28_kb) and a signed mapping ((x+1)/2, zero -> mid-grey) is reported beside
    it (S_signed_crf28_kb, E_signed_crf28_kb).
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out = {}

    def enc(tensor, label, crf):
        p = work_dir / f"{label}_crf{crf}.mp4"
        encode_frames_h264(to_frames(tensor), p, crf=crf, fps=FPS)
        return get_file_size_kb(p), p

    out["X_crf23_kb"], _ = enc(X_input, "X", CRF_REF)
    out["X_crf28_kb"], _ = enc(X_input, "X", CRF_COMP)
    out["L_crf28_kb"], _ = enc(L, "L", CRF_COMP)
    out["LS_crf28_kb"], ls_path = enc(L + S, "LS", CRF_COMP)
    out["S_crf28_kb"], _ = enc(S, "S", CRF_COMP)
    out["E_crf28_kb"], _ = enc(E, "E", CRF_COMP)
    out["S_signed_crf28_kb"], _ = enc((S + 1.0) / 2.0, "S_signed", CRF_COMP)
    out["E_signed_crf28_kb"], _ = enc((E + 1.0) / 2.0, "E_signed", CRF_COMP)
    return out, ls_path


def main():
    ap = argparse.ArgumentParser(description="One Phase 3 SS-RTD run")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--factor", type=float, required=True)
    ap.add_argument("--lam", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0, help="noise seed; ignored when clean")
    ap.add_argument("--arm", default="", help="label recorded in the row, set by the runner")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--keep-components", action="store_true",
                    help="also save full float32 L/S/E (66 MB each) -- figure videos only")
    args = ap.parse_args()

    out = Path(args.out_dir)
    if any(bad in str(out) for bad in _FORBIDDEN):
        sys.exit(f"refusing to write near a frozen baseline path: {out}")
    out.mkdir(parents=True, exist_ok=True)

    proc = psutil.Process()
    t_start = datetime.now()
    t_run = time.perf_counter()
    print(f"[worker] {args.video_id} {args.condition} factor={args.factor} "
          f"lam={args.lam} seed={args.seed} start {t_start:%H:%M:%S}", flush=True)

    registry = load_registry(PROJECT_DIR / "video_registry.csv")
    hit = registry[registry.short_id == args.video_id]
    if hit.empty:
        sys.exit(f"{args.video_id} is not in video_registry.csv")
    row = hit.iloc[0]
    path = PROJECT_DIR / "data" / "videos" / row["original_filename"]

    frames = load_video_frames(path, max_frames=300)           # (T, H, W) in [0,1]
    fg_density = compute_foreground_density(frames)             # method-independent
    X_clean = frames_to_tensor(frames)                          # (H, W, T)
    del frames

    if args.condition == "impulse10":
        X_input, noise_mask = add_impulse_noise(X_clean, NOISE_RATIO, args.seed, scale=1.0)
    else:
        X_input, noise_mask = X_clean, None

    ranks = tucker_ranks(X_clean.shape)
    print(f"[worker] tensor {X_clean.shape} fg_density {fg_density}% "
          f"ranks {ranks} -> {feasible_ranks(X_clean.shape, ranks)}", flush=True)

    t0 = time.perf_counter()
    r = ssrtd_real(X_input, lam=args.lam, factor=args.factor,
                   max_iter=MAX_ITER, tol=TOL, log=True, verbose=True)
    admm_seconds = time.perf_counter() - t0
    L, S, E = r["L"], r["S"], r["E"]

    # ---- per-iteration log (output contract) -------------------------------
    hist = pd.DataFrame(r["history"])
    for k, v in (("seed", args.seed), ("lam", args.lam), ("factor", args.factor),
                 ("condition", args.condition), ("video_id", args.video_id),
                 ("method", "ssrtd_real")):
        hist.insert(0, k, v)
    hist.to_csv(out / "history.csv", index=False)

    # ---- metrics ----------------------------------------------------------
    X_frames = to_frames(X_input)
    LS_frames = to_frames(L + S)
    psnr_LS, _, _ = compute_psnr_sequence(X_frames, LS_frames)
    ssim_LS, _, _ = compute_ssim_sequence(X_frames, LS_frames)
    psnr_L, _, _ = compute_psnr_sequence(X_frames, to_frames(L))
    ssim_L, _, _ = compute_ssim_sequence(X_frames, to_frames(L))

    def l1(A):
        return float(np.abs(A).sum())

    resid = float(np.linalg.norm((X_input - L - S - E).ravel())
                  / np.linalg.norm(X_input.ravel()))
    stats = {"l1_L": l1(L), "l1_S": l1(S), "l1_E": l1(E),
             "constraint_residual_rel": round(resid, 8),
             "psnr_LS_vs_X": psnr_LS, "ssim_LS_vs_X": ssim_LS,
             "psnr_L_vs_X": psnr_L, "ssim_L_vs_X": ssim_L}
    stats.update(support_stats(S, "S"))
    stats.update(support_stats(E, "E"))
    stats.update(se_overlap(S, E))

    if args.condition == "impulse10":
        clean_frames = to_frames(X_clean)
        p_noisy, _, _ = compute_psnr_sequence(clean_frames, X_frames)
        p_ls, _, _ = compute_psnr_sequence(clean_frames, LS_frames)
        s_ls, _, _ = compute_ssim_sequence(clean_frames, LS_frames)
        p_l, _, _ = compute_psnr_sequence(clean_frames, to_frames(L))
        stats.update({"psnr_noisy_vs_clean": p_noisy, "psnr_LS_vs_clean": p_ls,
                      "ssim_LS_vs_clean": s_ls, "psnr_L_vs_clean": p_l})
        stats.update(noise_recovery(E, noise_mask, X_clean, X_input))

    # ---- H.264 ------------------------------------------------------------
    t0 = time.perf_counter()
    sizes, ls_path = h264_sizes(X_input, L, S, E, out / "h264")
    decoded = frames_to_tensor(load_video_frames(ls_path, max_frames=X_clean.shape[2]))
    n = min(decoded.shape[2], X_clean.shape[2])
    p_h, _, _ = compute_psnr_sequence(X_frames[:n], to_frames(decoded)[:n])
    s_h, _, _ = compute_ssim_sequence(X_frames[:n], to_frames(decoded)[:n])
    sizes.update({"psnr_LS_after_h264": p_h, "ssim_LS_after_h264": s_h,
                  "h264_frames_decoded": int(n)})
    h264_seconds = time.perf_counter() - t0
    del decoded

    # ---- artifacts --------------------------------------------------------
    np.savez_compressed(out / "L_tucker.npz", G=r["G"].astype(np.float32),
                        **{f"U{i}": U.astype(np.float32) for i, U in enumerate(r["Us"])})
    supports = {"shape": np.array(X_clean.shape)}
    for name, A in (("S", S), ("E", E)):
        for t in THRESHOLDS:
            supports[f"{name}_gt{_tag(t)}"] = np.packbits(np.abs(A) > t)
        supports[f"{name}_l1_per_frame"] = np.abs(A).sum(axis=(0, 1)).astype(np.float32)
    np.savez_compressed(out / "supports.npz", **supports)
    if noise_mask is not None:
        np.savez_compressed(out / "noise_mask.npz", mask=np.packbits(noise_mask),
                            shape=np.array(noise_mask.shape), seed=np.array(args.seed))
    if args.keep_components:
        np.savez_compressed(out / "components.npz", L=L.astype(np.float32),
                            S=S.astype(np.float32), E=E.astype(np.float32))

    total_seconds = time.perf_counter() - t_run
    mi = proc.memory_info()
    summary = {
        "method": "ssrtd_real", "condition": args.condition, "arm": args.arm,
        "video_id": args.video_id, "original_filename": row["original_filename"],
        "factor": args.factor, "lam": args.lam, "seed": args.seed,
        "noise_ratio": NOISE_RATIO if args.condition == "impulse10" else None,
        "H": int(X_clean.shape[0]), "W": int(X_clean.shape[1]), "T": int(X_clean.shape[2]),
        "foreground_density": fg_density,
        "max_iter": MAX_ITER, "tol": TOL,
        "ranks_attainable": list(feasible_ranks(X_clean.shape, ranks)),
        "n_iter": r["n_iter"], "converged": r["converged"],
        "admm_seconds": round(admm_seconds, 2), "h264_seconds": round(h264_seconds, 2),
        "total_seconds": round(total_seconds, 2),
        "peak_wset_mb": round(mi.peak_wset / 2**20, 1),
        "relChg_L_final": r["history"][-1]["relChg_L"],
        "relChg_S_final": r["history"][-1]["relChg_S"],
        "relChg_E_final": r["history"][-1]["relChg_E"],
        "err_f_final": r["history"][-1]["err_f"], "err_X_final": r["history"][-1]["err_X"],
        "beta_f_final": r["beta_f"], "beta_X_final": r["beta_X"],
        "beta_X_grew_n": int(hist["beta_X_grew"].sum()),
        "s_update_path": "half",
        "started_at": t_start.isoformat(timespec="seconds"),
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        **stats, **sizes,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))   # LAST: the marker

    print(f"[worker] done {args.video_id} {args.condition}: {r['n_iter']} iters, "
          f"{total_seconds/60:.1f} min ({admm_seconds/60:.1f} ADMM + {h264_seconds:.0f}s H.264), "
          f"peak {summary['peak_wset_mb']:.0f} MB, psnr(L+S vs X) {psnr_LS:.2f} dB, "
          f"SE overlap {stats.get('SE_overlap_005')}%", flush=True)


if __name__ == "__main__":
    main()
