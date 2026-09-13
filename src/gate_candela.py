"""
(g2) VERIFICATION GATE — reproduce Shen et al. 2022, Fig. 3, on Candela.

IMPLEMENTATION_PLAN.md is explicit: no VIRAT run until this gate passes. The gate
runs our SS-RTD implementation on the dataset, noise model and lambda the paper
used for its own convergence figure, and compares the result against numbers read
off that figure.

Paper setup (section IV-A1):
  data    SBI "Candela", first 80 frames, grayscale 288 x 352 -> tensor 288x352x80.
          The frames come from SBI's zip Candela_m1.10.zip, which holds SBI's
          subset (ORIGINAL frames 85-435); its first 80 files are original frames
          85-164. That is the paper's actual source -- see the note at
          SBI_SUBSET_FRAMES below before changing anything about the frame count.
  noise   "For each image, 10% of pixels are randomly selected to set as random
          integers in [0, 255], and the positions of the contaminated pixels are
          unknown."  Random-valued impulse noise, applied by REPLACEMENT.
  lambda  0.4
  scale   pixel values in [0, 255]. The paper's PSNR uses 255^2, so we keep that
          scale here rather than the [0, 1] normalization used for VIRAT.

Targets, read from the rendered figures (approximate, +/- ~0.003):
  Fig. 4  relErr_L at lambda = 0.4  ~ 0.013 (the curve's minimum region)
  Fig. 3  relErr_L  0.062 at iter 1 -> 0.017 at 20 -> plateau ~0.013 from ~40
          relChg_S  off-scale early -> 0.08 at 10 -> 0.01 at 30 -> ~0 by 80
          relChg_L  0 at iter 1 -> peak ~0.035 near iter 4 -> 0.002 by 30 -> ~0

Acceptance criteria. Pass/fail is decided ONLY by criteria grounded in the paper.
Our additional diagnostics are reported but do not gate.
  C1  run completes; every logged numeric field finite (bar the documented inf on
      relChg_E while E is identically zero)
  C2  final relErr_L within a factor of 2 of the paper's 0.013, i.e. in
      [0.0065, 0.026], and plateaued (change over the last 20 iterations
      < 0.002). Needs the ground-truth background.
  C3  convergence shape matches Fig. 3:
        a) relChg_L at iteration 1 < 1e-8. Fig. 3 starts it at 0, and our
           initialization predicts exactly that: X_tilde = L_0 on iteration 1.
        b) final relChg_L and relChg_S both < 0.005 (Fig. 3: ~0 by 80-100)
        c) relChg_S decays: its value at iteration 30 is below iteration 10's
  D1  (reported) E captures the injected noise: recall on detectable noise pixels,
      and precision of E's support against the known noise mask
  D2  (reported) our curves against the digitized Fig. 3 points, side by side
  D3  (reported) peak working set and wall time of the full loop -- the memory
      number the (g) carry-forward decisions are waiting on
  D4  (reported) PSNR and SSIM of L against the ground-truth background, per frame
      and averaged, next to Table I's SS-RTD row for Candela at 10% noise
      (43.27 dB, 0.9019). STANDARD per-pixel PSNR is used, because the printed
      formula omits the division by pixel count and Table I's numbers only fit
      the standard one (PAPER_NOTES.md item 15). The literal formula's value is
      reported alongside, to show the gap.

factor: runs 2.0 (eq. 12 as printed) by default; --factor both adds 1.0 (the value
Appendix A implies). Because this is the paper's own data and figure, whichever
factor reproduces Fig. 3 is direct evidence of what the authors ran -- the most
informative place to settle PAPER_NOTES.md item 11.

Outputs (results/gate_candela/, gitignored; Output Contract filenames):
  history_factor{F}.csv      per-iteration log, with method / dataset / factor
  components_factor{F}.npz   L, S, E, noise mask (float32 storage, float64 compute)
  summary.json               config, data provenance, criteria, verdict
  fig3_reproduction.png      our curves with the digitized paper points overlaid
  decomposition_frame.png    one frame: clean, noisy, L, S, E, noise mask
Data files are written BEFORE any plotting, so a plotting failure cannot discard
a long run.

Run from the project directory, ONLY once data/candela/ is in place:
    python -m src.gate_candela --check-data     # confirm inputs, no solve
    python -m src.gate_candela                  # factor 2.0
    python -m src.gate_candela --factor both    # factors 2.0 and 1.0
"""

import argparse
import ctypes
import hashlib
import json
import re
import sys
import time
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from src.ssrtd_real import feasible_ranks, ssrtd_real, tucker_ranks

PROJECT_DIR = Path(__file__).parent.parent
DEFAULT_FRAMES_DIR = PROJECT_DIR / "data" / "candela"
DEFAULT_OUT_DIR = PROJECT_DIR / "results" / "gate_candela"

PAPER_SHAPE = (288, 352)        # rows x cols; SBI lists the same size as 352x288 (W x H)
PAPER_N_FRAMES = 80
# ---------------------------------------------------------------------------------
# WHICH CANDELA FRAMES THIS IS -- read before "fixing" the frame count.
#
# The gate input is SBI's zip, Candela_m1.10.zip: 350 PNG frames that are SBI's
# "used frames" subset, ORIGINAL frames 85-435 of the Candela sequence. Its file
# _000000.png is original frame 85, so the gate's first 80 files are original
# frames 85-164. That is deliberate and it is what the paper used.
#
# The SS-RTD paper (IV-A1) says Candela "has 855 image frames" and that "the first
# 80 image frames in the sequence are used". Read alone, that suggests frames 0-79
# of a full 855-frame video. The evidence says otherwise:
#   * IV-B names the source explicitly: "Candela ..., Caviar1, and Caviar2 from
#     SBI dataset [45]", with footnote 7 pointing at the SBI page.
#   * Its Caviar1/Caviar2 descriptions are word-for-word SBI's table text.
#   * Its Caviar tensors are 256 x 384 -- SBI's CROP of the 384 x 288 originals.
#     That size exists only in SBI's packaging.
#   * "855 frames" is SBI's "original frames 0-855" column, which describes the
#     source video, not the contents of SBI's download.
# SBI states its downloads contain only the used subsets, and the original
# CANDELA source SBI links to returns HTTP 404 (checked 2026-09-13). So there is
# no full 855-frame sequence to obtain, and the paper never used one.
#
# The count check below guards against an INCOMPLETE extraction or a different
# release -- not against the subset itself, which is the correct input.
# ---------------------------------------------------------------------------------
SBI_SUBSET_FRAMES = 350          # Candela_m1.10.zip, original frames 85-435
PAPER_NOISE_RATIO = 0.10
PAPER_LAMBDA = 0.4
PAPER_RELERR_L = 0.013          # Fig. 4 at lambda = 0.4
TABLE_I_CANDELA_10PCT = {"psnr": 43.27, "ssim": 0.9019}   # SS-RTD ("Proposed") row

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".avi", ".mp4", ".mov", ".mkv", ".wmv", ".mpg", ".mpeg"}
GT_NAME = re.compile(
    r"(?:^|[^a-z0-9])(gt|groundtruth|ground[_-]truth|background)(?:[^a-z0-9]|$)",
    re.IGNORECASE)
GT_DIRS = {"gt", "groundtruth", "ground_truth", "ground-truth"}

# Digitized from the rendered Fig. 3 (300 dpi). Approximate, +/- ~0.003.
FIG3_REFERENCE = {
    "relChg_L": {1: 0.000, 4: 0.035, 5: 0.0285, 10: 0.0085, 15: 0.0053,
                 20: 0.0035, 25: 0.0021, 30: 0.0019, 40: 0.0016, 50: 0.0013,
                 60: 0.0010, 80: 0.0005, 100: 0.000},
    "relChg_S": {10: 0.0805, 15: 0.052, 20: 0.0333, 25: 0.0173, 30: 0.0099,
                 35: 0.0096, 40: 0.0067, 45: 0.0040, 50: 0.0029, 55: 0.0019,
                 60: 0.0013, 70: 0.0010, 80: 0.0005, 100: 0.000},
    "relErr_L": {1: 0.0626, 5: 0.0474, 10: 0.0341, 15: 0.0240, 20: 0.0168,
                 25: 0.0165, 30: 0.0144, 35: 0.0136, 40: 0.0125, 60: 0.0125,
                 80: 0.0125, 100: 0.0125},
}

# Chart tokens: dataviz reference palette, light mode. Categorical slots 1-3 in
# fixed order, validated (scripts/validate_palette.js): CVD dE 9.2, normal-vision
# dE 27.6. Aqua is 2.74:1 on the surface, so every series also gets a direct
# label and a legend entry, and the CSV is the table view.
SURFACE, INK_PRIMARY, INK_SECONDARY = "#fcfcfb", "#0b0b0b", "#52514e"
INK_MUTED, GRIDLINE, BASELINE = "#898781", "#e1e0d9", "#c3c2b7"
DIVERGING = ("#2a78d6", "#f0efec", "#e34948")      # blue <-> gray <-> red
SERIES = [  # (log key, colour, line style, marker, label) -- colour follows entity
    ("relChg_L", "#2a78d6", "-", "o", "relChg L"),
    ("relChg_S", "#eb6834", "-.", "s", "relChg S"),
    ("relErr_L", "#1baf7a", "--", "v", "relErr L"),
]


# ---------------------------------------------------------------- inputs
def _natural_key(path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def _is_gt(path, root):
    parts = [p.lower() for p in path.relative_to(root).parts]
    return any(p in GT_DIRS for p in parts[:-1]) or bool(GT_NAME.search(path.stem))


def _abort(msg):
    print(f"\nGATE NOT RUN: {msg}")
    sys.exit(2)


def find_inputs(frames_dir, gt_arg):
    """Resolve the frame source and the ground-truth background, loudly."""
    root = Path(frames_dir)
    if not root.is_dir():
        _abort(f"{root} does not exist. Put the Candela frames there first.")

    files = [p for p in root.rglob("*") if p.is_file()]
    images = [p for p in files if p.suffix.lower() in IMAGE_EXTS]
    videos = sorted(p for p in files if p.suffix.lower() in VIDEO_EXTS)
    gt_candidates = sorted(p for p in images if _is_gt(p, root))
    frames = sorted((p for p in images if not _is_gt(p, root)), key=_natural_key)

    if frames:
        dirs = sorted({str(p.parent) for p in frames})
        if len(dirs) > 1:
            _abort("frames found in more than one folder; pass --frames-dir "
                   "pointing at the one sequence folder:\n  " + "\n  ".join(dirs))
        source = ("images", frames)
    elif len(videos) == 1:
        source = ("video", videos[0])
    elif len(videos) > 1:
        _abort("several video files found; keep one:\n  "
               + "\n  ".join(map(str, videos)))
    else:
        _abort(f"no image frames or video file found under {root}.")

    if gt_arg:
        gt = Path(gt_arg)
        if not gt.is_file():
            _abort(f"--gt {gt} does not exist.")
    elif len(gt_candidates) == 1:
        gt = gt_candidates[0]
    elif len(gt_candidates) > 1:
        _abort("several ground-truth candidates found; choose one with --gt:\n  "
               + "\n  ".join(map(str, gt_candidates)))
    else:
        gt = None
    return source, gt


def _read_gray(path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)     # BT.601, as rgb2gray
    if img is None:
        _abort(f"could not read image {path}")
    return img


def total_frames(source):
    """Frames available in the whole sequence, not just the ones we will use."""
    kind, src = source
    if kind == "images":
        return len(src)
    cap = cv2.VideoCapture(str(src))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return count


def load_frames(source, n):
    """First n frames as a float64 (H, W, T) tensor on the paper's [0, 255] scale."""
    kind, src = source
    if kind == "images":
        if len(src) < n:
            _abort(f"only {len(src)} frames found; the paper uses the first {n}.")
        used = src[:n]
        frames = [_read_gray(p) for p in used]
        names = [p.name for p in used]
    else:
        cap = cv2.VideoCapture(str(src))
        frames = []
        while len(frames) < n:
            ok, bgr = cap.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
        cap.release()
        if len(frames) < n:
            _abort(f"video {src} yielded only {len(frames)} frames; need {n}.")
        names = [f"{src.name}#{i}" for i in range(n)]

    stack = np.stack(frames, axis=2)
    if stack.shape[:2] != PAPER_SHAPE:
        _abort(f"frames are {stack.shape[0]}x{stack.shape[1]}; the paper's Candela "
               f"is {PAPER_SHAPE[0]}x{PAPER_SHAPE[1]}. Not resizing silently -- a "
               f"different resolution would not be a reproduction.")
    digest = hashlib.sha256(np.ascontiguousarray(stack).tobytes()).hexdigest()
    return stack.astype(np.float64), names, digest


def load_ground_truth(gt_path, T):
    if gt_path is None:
        return None
    gt = _read_gray(gt_path)
    if gt.shape != PAPER_SHAPE:
        _abort(f"ground truth {gt_path} is {gt.shape}, expected {PAPER_SHAPE}.")
    return np.repeat(gt.astype(np.float64)[:, :, None], T, axis=2)


def add_impulse_noise(X_clean, ratio, seed):
    """
    Paper IV-A1: in EACH frame, a fraction `ratio` of pixel positions (chosen
    without replacement) is REPLACED by a uniform random integer in [0, 255].
    Not salt-and-pepper, and not additive.
    """
    rng = np.random.default_rng(seed)
    H, W, T = X_clean.shape
    k = int(round(ratio * H * W))
    X = X_clean.copy()
    mask = np.zeros(X.shape, dtype=bool)
    for t in range(T):
        rows, cols = np.unravel_index(rng.choice(H * W, size=k, replace=False), (H, W))
        X[rows, cols, t] = rng.integers(0, 256, size=k).astype(np.float64)
        mask[rows, cols, t] = True
    return X, mask


# ---------------------------------------------------------------- memory
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


def _peak_mb():
    """Process peak working set in MB; nan off Windows. argtypes are required."""
    try:
        kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_MEMCOUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        c = _MEMCOUNTERS()
        c.cb = ctypes.sizeof(c)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),
                                          ctypes.byref(c), c.cb):
            return float("nan")
        return c.PeakWorkingSetSize / 2**20
    except (AttributeError, OSError):
        return float("nan")


# ---------------------------------------------------------------- criteria
def background_metrics(L, L_true):
    """
    PSNR and SSIM of the recovered background against the ground truth, computed
    per frame and averaged over frames, as the paper describes.

    PSNR is the STANDARD definition, 10*log10(255^2 / MSE) with MSE the mean over
    pixels. The paper prints 10*log10(255^2 / ||I - I_hat||_F^2), which sums rather
    than averages; Table I's magnitudes only fit the standard form (PAPER_NOTES.md
    item 15). The literal value is returned too, so the gap is visible.

    SSIM uses the Wang et al. 2004 settings (Gaussian window, sigma 1.5, population
    covariance), matching the reference the paper cites. No clipping is applied to
    L -- the paper does not describe any.
    """
    from skimage.metrics import structural_similarity

    psnr, psnr_literal, ssim = [], [], []
    for t in range(L.shape[2]):
        est, ref = L[:, :, t], L_true[:, :, t]
        sq = (est - ref) ** 2
        mse, total = float(sq.mean()), float(sq.sum())
        psnr.append(np.inf if mse == 0 else 10 * np.log10(255.0 ** 2 / mse))
        psnr_literal.append(np.inf if total == 0 else 10 * np.log10(255.0 ** 2 / total))
        ssim.append(float(structural_similarity(
            ref, est, data_range=255.0, gaussian_weights=True, sigma=1.5,
            use_sample_covariance=False)))
    return {"psnr_standard": float(np.mean(psnr)),
            "psnr_literal_formula": float(np.mean(psnr_literal)),
            "ssim": float(np.mean(ssim))}


def evaluate(r, X_clean, X_noisy, noise_mask, have_gt, L_true=None):
    hist = r["history"]
    by_iter = {h["iter"]: h for h in hist}
    out = {}

    numeric = [k for k in hist[0] if k not in ("beta_f_grew", "beta_X_grew")]
    bad = [(h["iter"], k) for h in hist for k in numeric
           if not np.isfinite(h[k])
           and not (k == "relChg_E" and np.isinf(h[k]))
           and not (k == "relErr_L" and not have_gt and np.isnan(h[k]))]
    out["C1_finite"] = {"passed": not bad,
                        "detail": f"{len(hist)} iterations x {len(numeric)} fields"
                                  + (f"; non-finite: {bad[:5]}" if bad else "")}

    if have_gt:
        final = hist[-1]["relErr_L"]
        plateau = abs(final - hist[-21]["relErr_L"]) if len(hist) > 20 else float("nan")
        lo, hi = PAPER_RELERR_L / 2, PAPER_RELERR_L * 2
        out["C2_relErr_L"] = {
            "passed": bool(lo <= final <= hi and np.isfinite(plateau) and plateau < 0.002),
            "final": final, "paper": PAPER_RELERR_L, "band": [lo, hi],
            "plateau_change_last20": plateau,
            "detail": f"final relErr_L {final:.4f} vs paper {PAPER_RELERR_L} "
                      f"(band {lo:.4f}-{hi:.4f}); change over last 20 iterations "
                      f"{plateau:.4f} (< 0.002)"}
    else:
        out["C2_relErr_L"] = {"passed": None,
                              "detail": "not evaluable: no ground-truth background"}

    c3a = hist[0]["relChg_L"] < 1e-8
    c3b = hist[-1]["relChg_L"] < 0.005 and hist[-1]["relChg_S"] < 0.005
    c3c = (10 in by_iter and 30 in by_iter
           and by_iter[30]["relChg_S"] < by_iter[10]["relChg_S"])
    out["C3_shape"] = {
        "passed": bool(c3a and c3b and c3c),
        "a_relChg_L_iter1": hist[0]["relChg_L"],
        "b_final_relChg_L": hist[-1]["relChg_L"],
        "b_final_relChg_S": hist[-1]["relChg_S"],
        "detail": (f"a) relChg_L iter 1 = {hist[0]['relChg_L']:.2e} (< 1e-8: {c3a}); "
                   f"b) final relChg_L {hist[-1]['relChg_L']:.2e}, relChg_S "
                   f"{hist[-1]['relChg_S']:.2e} (< 0.005: {c3b}); "
                   f"c) relChg_S iter 30 < iter 10: "
                   + (f"{by_iter[30]['relChg_S']:.4f} < {by_iter[10]['relChg_S']:.4f} ({c3c})"
                      if (10 in by_iter and 30 in by_iter)
                      else f"not evaluable, run ended at iteration {len(hist)} (False)"))}

    support = r["E"] != 0.0
    detectable = noise_mask & (np.abs(X_noisy - X_clean) > 30.0)
    recall = float(support[detectable].mean()) if detectable.any() else float("nan")
    precision = (float((support & noise_mask).sum() / support.sum())
                 if support.any() else float("nan"))
    out["D1_noise_capture"] = {
        "reported_only": True, "recall_detectable": recall, "precision": precision,
        "E_nonzero_fraction": float(support.mean()),
        "detail": f"recall on noise pixels differing by >30 grey levels {recall:.3f}; "
                  f"precision of E's support {precision:.3f}; E nonzero "
                  f"{100 * support.mean():.1f}% (injected {100 * noise_mask.mean():.1f}%)"}

    if L_true is not None:
        m = background_metrics(r["L"], L_true)
        out["D4_table_I"] = {
            "reported_only": True, **m,
            "paper_psnr": TABLE_I_CANDELA_10PCT["psnr"],
            "paper_ssim": TABLE_I_CANDELA_10PCT["ssim"],
            "detail": f"PSNR {m['psnr_standard']:.2f} dB vs Table I "
                      f"{TABLE_I_CANDELA_10PCT['psnr']} (standard definition; the "
                      f"printed formula would give {m['psnr_literal_formula']:.2f}); "
                      f"SSIM {m['ssim']:.4f} vs {TABLE_I_CANDELA_10PCT['ssim']}"}
    else:
        out["D4_table_I"] = {"reported_only": True,
                             "detail": "not evaluable: no ground-truth background"}

    table = []
    for key, ref in FIG3_REFERENCE.items():
        for it, paper_val in ref.items():
            if it in by_iter:
                table.append({"series": key, "iter": it, "paper": paper_val,
                              "ours": by_iter[it][key]})
    out["D2_vs_fig3"] = {"reported_only": True, "points": table}
    return out


def verdict_for(criteria):
    c2 = criteria["C2_relErr_L"]["passed"]
    if c2 is None:
        return "INCOMPLETE"
    return "PASS" if (criteria["C1_finite"]["passed"] and c2
                      and criteria["C3_shape"]["passed"]) else "FAIL"


# ---------------------------------------------------------------- plots
def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRIDLINE, linewidth=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY)


def plot_fig3(runs, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    n = len(runs)
    fig, axes = plt.subplots(1, n, figsize=(6.6 * n, 5.0), sharey=True,
                             squeeze=False, facecolor=SURFACE)
    YMAX = 0.15                                 # the paper's own y-limit

    for ax, run in zip(axes[0], runs):
        _style_axes(ax)
        hist = run["result"]["history"]
        iters = np.array([h["iter"] for h in hist])
        clipped = False
        for key, colour, ls, marker, label in SERIES:
            ys = np.array([h[key] for h in hist], dtype=float)
            if np.all(np.isnan(ys)):
                continue
            ys_plot = np.where(np.isinf(ys), np.nan, ys)
            clipped |= bool(np.nanmax(ys_plot) > YMAX)
            ax.plot(iters, ys_plot, color=colour, linewidth=2, linestyle=ls, zorder=3)

            ref = FIG3_REFERENCE[key]
            ax.plot(list(ref), list(ref.values()), linestyle="none", marker=marker,
                    markersize=8, markerfacecolor=SURFACE, markeredgecolor=colour,
                    markeredgewidth=2, zorder=4)

            # direct label at an informative, non-colliding point; ink, not colour
            finite = np.isfinite(ys_plot) & (ys_plot <= YMAX)
            if not finite.any():
                continue
            if key == "relChg_L":
                idx = int(np.nanargmax(np.where(finite, ys_plot, -np.inf)))
            elif key == "relChg_S":
                cand = np.where(finite & (ys_plot <= 0.06))[0]
                idx = int(cand[0]) if len(cand) else int(np.where(finite)[0][0])
            else:
                idx = int(np.where(finite)[0][min(len(np.where(finite)[0]) - 1, 69)])
            ax.annotate(label, (iters[idx], ys_plot[idx]), xytext=(8, 8),
                        textcoords="offset points", color=INK_SECONDARY,
                        fontsize=9, zorder=5)

        r = run["result"]
        ax.set_xlim(0, max(100, int(iters.max())))
        ax.set_ylim(0, YMAX)
        ax.set_xlabel("Iteration", color=INK_SECONDARY)
        status = "converged" if r["converged"] else "ran to cap"
        ax.set_title(f"factor {run['factor']:g}  ·  {r['n_iter']} iterations, {status}"
                     f"  ·  {run['verdict']}", color=INK_PRIMARY, fontsize=11, loc="left")
        if clipped:
            ax.text(0.99, 0.99, "values above 0.15 clipped, as in the paper",
                    transform=ax.transAxes, ha="right", va="top",
                    color=INK_MUTED, fontsize=8)

    axes[0][0].set_ylabel("Relative change / error", color=INK_SECONDARY)
    handles = [Line2D([], [], color=c, linestyle=ls, linewidth=2, marker=m,
                      markersize=8, markerfacecolor=SURFACE, markeredgewidth=2,
                      label=lab) for _, c, ls, m, lab in SERIES]
    handles += [Line2D([], [], color=INK_MUTED, linewidth=2, label="line: this implementation"),
                Line2D([], [], color=INK_MUTED, linestyle="none", marker="o",
                       markersize=8, markerfacecolor=SURFACE, markeredgewidth=2,
                       label="hollow marker: paper Fig. 3 (digitized, approx.)")]
    leg = axes[0][-1].legend(handles=handles, loc="upper right",
                             bbox_to_anchor=(1.0, 0.93), frameon=False, fontsize=9)
    for text in leg.get_texts():
        text.set_color(INK_SECONDARY)
    fig.suptitle("Fig. 3 reproduction — SBI Candela, 10% random-valued impulse "
                 "noise, λ = 0.4", color=INK_PRIMARY, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def plot_frame(X_clean, X_noisy, run, noise_mask, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    r = run["result"]
    t = X_clean.shape[2] // 2
    div = LinearSegmentedColormap.from_list("diverging", DIVERGING)

    def sym(a):
        v = float(np.percentile(np.abs(a), 99)) or 1.0
        return -v, v

    panels = [
        ("Clean frame", X_clean[:, :, t], "gray", (0, 255)),
        ("Noisy input (10% impulse)", X_noisy[:, :, t], "gray", (0, 255)),
        ("Injected noise positions", noise_mask[:, :, t].astype(float), "gray", (0, 1)),
        ("L — static background", r["L"][:, :, t], "gray", (0, 255)),
        ("S — smooth foreground", r["S"][:, :, t], div, sym(r["S"][:, :, t])),
        ("E — sparse noise", r["E"][:, :, t], div, sym(r["E"][:, :, t])),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.0), facecolor=SURFACE)
    for ax, (title, img, cmap, (vmin, vmax)) in zip(axes.flat, panels):
        im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title, color=INK_PRIMARY, fontsize=10, loc="left")
        ax.axis("off")
        if cmap is div:
            cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
            cb.ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY, labelsize=8)
            cb.outline.set_edgecolor(BASELINE)
    fig.suptitle(f"Decomposition, frame {t + 1} of {X_clean.shape[2]}  ·  "
                 f"factor {run['factor']:g}", color=INK_PRIMARY, fontsize=12,
                 x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- main
def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    return o


def main():
    ap = argparse.ArgumentParser(description="(g2) Candela verification gate")
    ap.add_argument("--frames-dir", default=str(DEFAULT_FRAMES_DIR))
    ap.add_argument("--gt", default=None, help="ground-truth background image")
    ap.add_argument("--n-frames", type=int, default=PAPER_N_FRAMES)
    ap.add_argument("--noise-ratio", type=float, default=PAPER_NOISE_RATIO)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lam", type=float, default=PAPER_LAMBDA)
    ap.add_argument("--factor", choices=["2.0", "1.0", "both"], default="2.0")
    ap.add_argument("--max-iter", type=int, default=100)
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--out", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--check-data", action="store_true",
                    help="resolve and load inputs, report them, then stop")
    ap.add_argument("--allow-any-length", action="store_true",
                    help="skip the check that the folder holds SBI's 350-frame "
                         "Candela_m1.10 subset (use only if you know why)")
    args = ap.parse_args()

    print("=" * 76)
    print("(g2) VERIFICATION GATE — Shen et al. 2022 Fig. 3 on SBI Candela")
    print("=" * 76)

    source, gt_path = find_inputs(args.frames_dir, args.gt)
    seq_total = total_frames(source)
    if seq_total != SBI_SUBSET_FRAMES and not args.allow_any_length:
        _abort(f"the folder holds {seq_total} frames; SBI's Candela_m1.10.zip -- the "
               f"paper's actual source -- has {SBI_SUBSET_FRAMES} (original frames "
               f"85-435). A different count usually means an incomplete extraction or "
               f"a different release. Re-extract the SBI zip, or pass "
               f"--allow-any-length if the difference is understood.")
    X_clean, names, digest = load_frames(source, args.n_frames)
    L_true = load_ground_truth(gt_path, X_clean.shape[2])
    ranks = tucker_ranks(X_clean.shape)

    print(f"  frames      : {source[0]}, {len(names)} used, {names[0]} ... {names[-1]}")
    print(f"  tensor      : {X_clean.shape}, range [{X_clean.min():.0f}, "
          f"{X_clean.max():.0f}], mean {X_clean.mean():.2f}")
    print(f"  sha256      : {digest[:16]}...")
    print(f"  ground truth: {gt_path if gt_path else 'NONE -- C2 will not be evaluable'}")
    print(f"  ranks       : {ranks} requested -> {feasible_ranks(X_clean.shape, ranks)} "
          f"attainable (PAPER_NOTES.md item 1)")
    if args.check_data:
        print("\n--check-data: inputs resolved and loaded. No solve performed.")
        return 0

    X_noisy, noise_mask = add_impulse_noise(X_clean, args.noise_ratio, args.seed)
    print(f"  noise       : {100 * noise_mask.mean():.2f}% of pixels replaced by "
          f"U{{0..255}}, seed {args.seed}")
    factors = {"2.0": [2.0], "1.0": [1.0], "both": [2.0, 1.0]}[args.factor]
    print(f"  lambda      : {args.lam}   factor(s): {factors}   max_iter "
          f"{args.max_iter}   tol {args.tol:g}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for factor in factors:
        print(f"\n--- solving, factor {factor:g} "
              f"(expect roughly 15-35 min at literal settings) ---")
        t0 = time.perf_counter()
        r = ssrtd_real(X_noisy, lam=args.lam, max_iter=args.max_iter, tol=args.tol,
                       factor=factor, L_true=L_true, verbose=True)
        wall = time.perf_counter() - t0
        peak = _peak_mb()

        criteria = evaluate(r, X_clean, X_noisy, noise_mask, L_true is not None,
                            L_true=L_true)
        criteria["D3_resources"] = {"reported_only": True, "wall_seconds": wall,
                                    "seconds_per_iteration": wall / max(r["n_iter"], 1),
                                    "process_peak_working_set_mb": peak}
        verdict = verdict_for(criteria)
        run = {"factor": factor, "result": r, "criteria": criteria, "verdict": verdict}
        runs.append(run)

        # data first -- plots can fail without costing the run
        tag = f"{factor:g}"
        hist = pd.DataFrame(r["history"])
        hist.insert(0, "method", "ssrtd_real")
        hist.insert(1, "dataset", "candela")
        hist.insert(2, "factor", factor)
        hist.insert(3, "lam", args.lam)
        hist.insert(4, "seed", args.seed)
        hist.to_csv(out / f"history_factor{tag}.csv", index=False)
        np.savez_compressed(out / f"components_factor{tag}.npz",
                            L=r["L"].astype(np.float32), S=r["S"].astype(np.float32),
                            E=r["E"].astype(np.float32), noise_mask=noise_mask)

        print(f"\n  factor {factor:g}: {verdict}")
        for name, c in criteria.items():
            if name.startswith("D2"):
                continue
            flag = ("REPORT" if c.get("reported_only")
                    else {True: "PASS", False: "FAIL", None: "N/A"}[c["passed"]])
            detail = c.get("detail") or ", ".join(
                f"{k}={v:.3g}" for k, v in c.items() if isinstance(v, float))
            print(f"    [{flag:6s}] {name}: {detail}")
        print(f"    wall {wall/60:.1f} min, {wall/max(r['n_iter'],1):.2f} s/iter, "
              f"peak working set {peak:.0f} MB")

    summary = {
        "gate": "g2_candela_fig3",
        "config": vars(args),
        "data": {"source_kind": source[0],
                 "sequence_total_frames": seq_total,
                 "frame_source_note": "SBI Candela_m1.10.zip subset (original frames "
                                      "85-435); first 80 files = original frames "
                                      "85-164. This is the paper's actual source.",
                 "frames_used": len(names),
                 "first_frame": names[0], "last_frame": names[-1],
                 "shape": list(X_clean.shape), "sha256": digest,
                 "ground_truth": str(gt_path) if gt_path else None,
                 "ranks_requested": list(ranks),
                 "ranks_attainable": list(feasible_ranks(X_clean.shape, ranks))},
        "paper_targets": {"relErr_L_fig4_lambda_0.4": PAPER_RELERR_L,
                          "fig3_digitized": FIG3_REFERENCE},
        "runs": [{"factor": run["factor"], "verdict": run["verdict"],
                  "n_iter": run["result"]["n_iter"],
                  "converged": run["result"]["converged"],
                  "criteria": run["criteria"]} for run in runs],
    }
    (out / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2))

    try:
        plot_fig3(runs, out / "fig3_reproduction.png")
        plot_frame(X_clean, X_noisy, runs[0], noise_mask, out / "decomposition_frame.png")
    except Exception as exc:                  # data is already safe on disk
        print(f"\n  WARNING: plotting failed ({type(exc).__name__}: {exc}); "
              f"CSV, NPZ and summary.json were written.")

    print("\n" + "=" * 76)
    for run in runs:
        print(f"  factor {run['factor']:g}: {run['verdict']}")
    passed = [run for run in runs if run["verdict"] == "PASS"]
    if passed:
        print(f"GATE PASSED for factor(s) {[run['factor'] for run in passed]} — the "
              f"implementation reproduces the paper's Fig. 3 behaviour.")
    else:
        print("GATE NOT PASSED — do not run VIRAT. Inspect fig3_reproduction.png.")
    print(f"outputs: {out}")
    print("=" * 76)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
