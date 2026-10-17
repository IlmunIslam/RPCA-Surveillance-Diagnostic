"""
Phase 3 batch runner -- the ONLY writer of results/metrics/ssrtd_real_results.csv.

Design: IMPLEMENTATION_PLAN.md (h). Batch decision and its reasoning:
RESEARCH_LOG.md section 8. Operational rules: PHASE3_NOTES.md.

Runs one subprocess per run (src.phase3_worker), so each run's memory is returned
to the OS when it exits, and appends one CSV row per completed run. A run is
identified by (video_id, condition, factor, lam, seed); resume skips rows already
in the CSV, and adopts a run whose summary.json exists but whose row is missing
(a crash between worker exit and append) rather than recomputing it.

Arms, in execution order -- the three arms on the 20-video sweep subset come first,
so analysis can start while the remaining 160 clean videos run:

  clean-subset     20 videos, clean,     factor 1.0
  noise-subset     20 videos, impulse10, factor 1.0, seed 0
  factor2-subset   20 videos, clean,     factor 2.0   (robustness, not a main result)
  clean-rest      160 videos, clean,     factor 1.0

Never two writers: a pid lock file refuses a second runner. Launch detached per
PHASE3_NOTES.md section 1, then the watchdog:

    python -u -m src.phase3_runner --dry-run
    python -u -m src.phase3_runner --smoke
    python -u -m src.phase3_runner                      # all arms, in order
    python -u -m src.phase3_runner --arms clean-subset
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).parent.parent
RESULTS_CSV = PROJECT_DIR / "results" / "metrics" / "ssrtd_real_results.csv"
MANIFEST = PROJECT_DIR / "results" / "metrics" / "ssrtd_real_manifest.json"
RUNS_DIR = PROJECT_DIR / "results" / "ssrtd_real" / "runs"
PLAN_CSV = PROJECT_DIR / "results" / "ssrtd_real" / "plan.csv"
LOCK_FILE = PROJECT_DIR / "results" / "ssrtd_real" / "runner.lock"
LOG_FILE = PROJECT_DIR / "logs" / "phase3_runner.log"
ERROR_LOG = PROJECT_DIR / "logs" / "phase3_errors.log"
SMOKE_DIR = PROJECT_DIR / "results" / "scratch" / "phase3_smoke"

LAM = 0.4                 # RESEARCH_LOG.md section 8: one lambda for every arm
TIMEOUT_S = 3600          # ~2.5x the measured 22 min ADMM + 2 min H.264
# Runs that also keep the full float32 L/S/E (160 MB per run compressed). Chosen as
# the sweep subset's density extremes plus its busiest scene, which is what the
# Phase 5 figures need (RESEARCH_PLAN.md figures 2 and 5: a decomposition example and
# the smooth-vs-sharp comparison). Everything else keeps only the Tucker factors of
# L and the packed supports, so a figure never requires re-solving a video.
FIGURE_VIDEOS = ("video_01",      # fg_density 4.263 -- busiest scene of all 180
                 "video_165",     # fg_density 0.013 -- emptiest of the subset
                 "video_108")     # fg_density 3.128 -- second busiest of the subset

# Column order of the results CSV. Written once as the header; every later row is
# reindexed onto it, so a missing field becomes empty rather than shifting columns.
COLUMNS = [
    "method", "condition", "arm", "video_id", "original_filename",
    "factor", "lam", "seed", "noise_ratio", "H", "W", "T", "foreground_density",
    "n_iter", "converged", "admm_seconds", "h264_seconds", "total_seconds",
    "peak_wset_mb",
    "relChg_L_final", "relChg_S_final", "relChg_E_final",
    "err_f_final", "err_X_final", "beta_f_final", "beta_X_final", "beta_X_grew_n",
    "constraint_residual_rel",
    "l1_L", "l1_S", "l1_E",
    "S_nonzero_pct", "S_gt001_pct", "S_gt005_pct",
    "E_nonzero_pct", "E_gt001_pct", "E_gt005_pct",
    "SE_overlap_005", "S_claimed_px", "SE_both_px",
    "psnr_LS_vs_X", "ssim_LS_vs_X", "psnr_L_vs_X", "ssim_L_vs_X",
    "X_crf23_kb", "X_crf28_kb", "L_crf28_kb", "LS_crf28_kb",
    "S_crf28_kb", "E_crf28_kb", "S_signed_crf28_kb", "E_signed_crf28_kb",
    "psnr_LS_after_h264", "ssim_LS_after_h264", "h264_frames_decoded",
    "E_recall", "E_precision", "E_recall_001", "E_precision_001",
    "E_recall_005", "E_precision_005",
    "E_recall_detectable_001", "E_recall_detectable_005", "noise_detectable_pct",
    "psnr_noisy_vs_clean", "psnr_LS_vs_clean", "ssim_LS_vs_clean", "psnr_L_vs_clean",
    "max_iter", "tol", "ranks_attainable", "s_update_path",
    "commit", "numpy_version", "started_at", "processed_at",
]

KEY = ("video_id", "condition", "factor", "lam", "seed")


# ----------------------------------------------------------------- environment
def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=str(PROJECT_DIR), capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def environment():
    """
    The numerical environment this batch ran on.

    Recorded because the trajectory depends on it: the ADMM amplifies
    rounding-level differences, so the same code on a different FFT or BLAS build
    reproduces the reported precision but not the exact numbers
    (RESEARCH_LOG.md section 6.6). Without this a reader cannot tell what to match.
    """
    import numpy
    cfg = getattr(numpy.__config__, "CONFIG", {}) or {}
    deps = cfg.get("Build Dependencies", {})

    def lib(name):
        d = deps.get(name, {}) or {}
        return {"name": d.get("name"), "version": d.get("version"),
                "detection": d.get("detection method")}

    try:
        import scipy
        scipy_version = scipy.__version__
    except Exception:
        scipy_version = None
    return {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "tz": time.strftime("%Z%z"),
        "commit": _git("rev-parse", "HEAD"),
        "commit_short": _git("rev-parse", "--short", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy_version,
        "blas": lib("blas"),
        "lapack": lib("lapack"),
        "fft_backend": "numpy.fft (pocketfft)",
        "s_update_path": "half (rfftn/irfftn)",
        "os": platform.platform(),
        "cpu": platform.processor(),
        "machine": platform.machine(),
        "thread_env": {k: os.environ.get(k) for k in
                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS")},
    }


def write_manifest(path=MANIFEST):
    """
    Append this start's environment to the manifest, never overwriting earlier
    entries -- so a numpy or OS change part way through a 80-hour batch is visible
    in the record instead of silently replacing what the earlier rows ran on.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if path.exists():
        try:
            prev = json.loads(path.read_text())
            entries = prev.get("entries", []) if isinstance(prev, dict) else list(prev)
        except Exception:
            entries = []
    env = environment()
    changed = None
    if entries:
        keys = ("commit", "numpy", "scipy", "blas", "lapack", "os", "python")
        changed = [k for k in keys if entries[-1].get(k) != env.get(k)]
    env["changed_since_previous_entry"] = changed
    entries.append(env)
    path.write_text(json.dumps(
        {"what": "numerical environment of every src.phase3_runner start that wrote to "
                 "ssrtd_real_results.csv; see RESEARCH_LOG.md 6.6 for why this is recorded",
         "entries": entries}, indent=2))
    return env


# ----------------------------------------------------------------- the plan
def subset_ids():
    """
    The 20 videos of the naive-baseline parameter sweep, re-derived rather than
    hard-coded, and cross-checked against the frozen sweep CSV (read only).
    """
    from src.param_sweep import select_videos
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        selection = select_videos()
    ids = [vid for vid, _d in selection]
    frozen = PROJECT_DIR / "results" / "metrics" / "param_sweep.csv"
    if frozen.exists():
        on_disk = sorted(pd.read_csv(frozen)["video_id"].astype(str).unique())
        if sorted(ids) != on_disk:
            sys.exit("select_videos() no longer matches the frozen param_sweep.csv "
                     f"subset:\n  derived: {sorted(ids)}\n  on disk: {on_disk}\n"
                     "Phase 3's noise and factor2 arms are defined as THAT subset "
                     "(RESEARCH_LOG.md section 8) -- resolve before running.")
    return ids


def all_ids():
    reg = pd.read_csv(PROJECT_DIR / "video_registry.csv")
    return sorted(reg["short_id"].astype(str).tolist(),
                  key=lambda v: int(v.split("_")[1]))


def build_plan(arms=None, smoke=False):
    """One dict per run, in execution order."""
    if smoke:
        return [
            dict(arm="smoke", video_id="video_01", condition="clean", factor=1.0,
                 lam=LAM, seed=0),
            dict(arm="smoke", video_id="video_01", condition="impulse10", factor=1.0,
                 lam=LAM, seed=0),
        ]
    sub = subset_ids()
    rest = [v for v in all_ids() if v not in set(sub)]
    spec = [
        ("clean-subset", sub, "clean", 1.0, 0),
        ("noise-subset", sub, "impulse10", 1.0, 0),
        ("factor2-subset", sub, "clean", 2.0, 0),
        ("clean-rest", rest, "clean", 1.0, 0),
    ]
    plan = []
    for arm, vids, cond, factor, seed in spec:
        if arms and arm not in arms:
            continue
        for vid in vids:
            plan.append(dict(arm=arm, video_id=vid, condition=cond,
                             factor=factor, lam=LAM, seed=seed))
    return plan


def run_dirname(run):
    return (f"{run['video_id']}__{run['condition']}__f{run['factor']:g}"
            f"__lam{run['lam']:g}__s{run['seed']}")


def key_of(d):
    return (str(d["video_id"]), str(d["condition"]), float(d["factor"]),
            float(d["lam"]), int(d["seed"]))


# ----------------------------------------------------------------- CSV + lock
def completed_keys(csv_path=RESULTS_CSV):
    if not csv_path.exists():
        return set()
    df = pd.read_csv(csv_path)
    if df.empty:
        return set()
    return {key_of(r) for _, r in df[list(KEY)].iterrows()}


def append_row(summary, csv_path, env):
    row = dict(summary)
    row["commit"] = env.get("commit_short") or env.get("commit")
    row["numpy_version"] = env.get("numpy")
    if isinstance(row.get("ranks_attainable"), (list, tuple)):
        row["ranks_attainable"] = "x".join(str(v) for v in row["ranks_attainable"])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in COLUMNS})
    missing = [k for k in row if k not in COLUMNS]
    return missing


def acquire_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            old = int(LOCK_FILE.read_text().split()[0])
        except Exception:
            old = None
        if old is not None and _pid_alive(old):
            sys.exit(f"another runner is alive (pid {old}); refusing to start a second "
                     f"writer. If that is wrong, delete {LOCK_FILE}")
        log(f"stale lock from pid {old} removed")
    LOCK_FILE.write_text(f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}")


def _pid_alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


MIN_FREE_GB = 2.0        # refuse to start another run below this


def free_gb(path=PROJECT_DIR):
    """Free space on the results volume, in GB."""
    import shutil as _sh
    return _sh.disk_usage(str(path)).free / 2**30


def _tail(path, n=2000):
    """Last n characters of a worker log, for the error record."""
    try:
        body = path.read_text(encoding="utf-8", errors="replace")[-n:]
        return f"--- {path.name} tail ---\n{body}"
    except OSError as exc:
        return f"(could not read {path}: {exc})"


def log_error(run, detail):
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"\n{'=' * 60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] FAILED "
                 f"{run_dirname(run)} (arm {run['arm']})\n{detail}\n")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Phase 3 batch runner (real SS-RTD)")
    ap.add_argument("--arms", default="", help="comma-separated subset of arm names")
    ap.add_argument("--smoke", action="store_true",
                    help="two-run smoke plan into results/scratch/phase3_smoke, "
                         "writing a scratch CSV, never the Phase 3 one")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    ap.add_argument("--retry-failed", action="store_true",
                    help="also re-queue runs that previously failed (no row, no summary)")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S)
    ap.add_argument("--limit", type=int, default=0, help="stop after N runs (testing)")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    plan = build_plan(arms or None, smoke=args.smoke)
    csv_path = (SMOKE_DIR / "smoke_results.csv") if args.smoke else RESULTS_CSV
    runs_root = (SMOKE_DIR / "runs") if args.smoke else RUNS_DIR

    done = completed_keys(csv_path)
    todo = [r for r in plan if key_of(r) not in done]
    if args.limit:
        todo = todo[:args.limit]

    if args.dry_run:
        print(f"plan: {len(plan)} runs ({len(plan) - len(todo)} already in "
              f"{csv_path.relative_to(PROJECT_DIR)}, {len(todo)} to run)")
        print(f"lambda {LAM}  timeout {args.timeout}s  results {csv_path}")
        print(f"runs under {runs_root}")
        by_arm = {}
        for r in plan:
            by_arm.setdefault(r["arm"], []).append(r)
        for arm, rs in by_arm.items():
            pend = [r for r in rs if key_of(r) in {key_of(t) for t in todo}]
            print(f"  {arm:<16} {len(rs):>3} runs, {len(pend):>3} pending  "
                  f"condition {rs[0]['condition']}, factor {rs[0]['factor']:g}  "
                  f"e.g. {run_dirname(rs[0])}")
        env = environment()
        print(f"disk: {free_gb():.1f} GB free (stops below {MIN_FREE_GB} GB)")
        print(f"environment: numpy {env['numpy']}, blas {env['blas'].get('name')} "
              f"{env['blas'].get('version')}, python {env['python']}, commit "
              f"{env['commit_short']}{' (DIRTY)' if env['dirty'] else ''}")
        return 0

    acquire_lock()
    env = write_manifest(MANIFEST if not args.smoke else SMOKE_DIR / "smoke_manifest.json")
    if env.get("dirty"):
        log("WARNING: working tree is dirty; rows will carry a commit that does not "
            "describe the code exactly")
    if env.get("changed_since_previous_entry"):
        log(f"NOTE: environment changed since the previous manifest entry: "
            f"{env['changed_since_previous_entry']}")

    PLAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(plan).to_csv(PLAN_CSV, index=False)
    log(f"disk: {free_gb():.1f} GB free on the results volume "
        f"(stops below {MIN_FREE_GB} GB); ~2.2 MB per run, 160 MB for each of "
        f"the {len(FIGURE_VIDEOS)} figure videos")
    log(f"runner start: {len(plan)} planned, {len(todo)} to run, lambda {LAM}, "
        f"timeout {args.timeout}s, csv {csv_path.name}, commit {env['commit_short']}")

    ok = failed = adopted = 0
    for n, run in enumerate(todo, 1):
        out_dir = runs_root / run_dirname(run)
        summary_path = out_dir / "summary.json"
        label = f"{run_dirname(run)} [{run['arm']}] ({n}/{len(todo)})"

        free = free_gb()
        if free < MIN_FREE_GB:
            log(f"STOPPING: only {free:.2f} GB free on the results volume "
                f"(need {MIN_FREE_GB} GB of headroom per run). "
                f"{len(todo) - n + 1} runs left; resume after freeing space.")
            break

        if summary_path.exists():
            # Worker finished but the row never landed -- adopt it, do not recompute.
            missing = append_row(json.loads(summary_path.read_text()), csv_path, env)
            adopted += 1
            log(f"ADOPTED existing summary {label}"
                + (f" (fields not in COLUMNS: {missing})" if missing else ""))
            continue

        cmd = [sys.executable, "-u", "-m", "src.phase3_worker",
               "--video-id", run["video_id"], "--condition", run["condition"],
               "--factor", str(run["factor"]), "--lam", str(run["lam"]),
               "--seed", str(run["seed"]), "--arm", run["arm"],
               "--out-dir", str(out_dir)]
        if run["video_id"] in FIGURE_VIDEOS:
            cmd.append("--keep-components")

        # The worker's output goes straight to a file rather than being captured in
        # memory: during an 80-hour batch the per-iteration log of the RUNNING worker
        # has to be readable (tail -f worker.log), which capture_output=True prevents
        # until the process exits.
        out_dir.mkdir(parents=True, exist_ok=True)
        worker_log = out_dir / "worker.log"
        log(f"START {label} -> {worker_log.relative_to(PROJECT_DIR)}")
        t0 = time.time()
        try:
            with open(worker_log, "a", encoding="utf-8") as fh:
                fh.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S}  "
                         f"{chr(32).join(cmd)}\n")
                fh.flush()
                res = subprocess.run(cmd, cwd=str(PROJECT_DIR), stdout=fh,
                                     stderr=subprocess.STDOUT, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            failed += 1
            log_error(run, f"TimeoutExpired after {args.timeout}s\n{_tail(worker_log)}")
            log(f"FAILED {label} -- timed out, continuing")
            continue
        mins = (time.time() - t0) / 60

        if res.returncode != 0 or not summary_path.exists():
            failed += 1
            why = "exit code" if res.returncode != 0 else "no summary.json written"
            log_error(run, f"{why} (exit {res.returncode})\n{_tail(worker_log)}")
            log(f"FAILED {label} ({why}, exit {res.returncode}) -- see "
                f"phase3_errors.log, continuing")
            continue

        missing = append_row(json.loads(summary_path.read_text()), csv_path, env)
        ok += 1
        log(f"DONE {label} in {mins:.1f} min"
            + (f" (fields not in COLUMNS: {missing})" if missing else ""))

    log(f"runner finished: {ok} ok, {adopted} adopted, {failed} failed, "
        f"{len(todo)} attempted")
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
