"""
Batch runner — processes all 180 VIRAT videos through run_pipeline sequentially.
Resumable: skips videos already present in all_results.csv.
"""

import argparse
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).parent.parent
VIDEO_DIR = r"S:\works\Video compression Research\RPCA_Hybrid_Project\data\videos"
REGISTRY = PROJECT_DIR / "video_registry.csv"
METRICS_CSV = PROJECT_DIR / "results" / "metrics" / "all_results.csv"
LOG_FILE = PROJECT_DIR / "logs" / "batch_run.log"
ERROR_LOG = PROJECT_DIR / "logs" / "batch_errors.log"


def get_completed_video_ids() -> set:
    if METRICS_CSV.exists():
        df = pd.read_csv(METRICS_CSV)
        return set(df["video_id"].astype(str).tolist())
    return set()


def log_message(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_error(video_id: str, stderr_tail: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"[{timestamp}] FAILED: {video_id}\n")
        f.write(f"--- stderr (last 500 chars) ---\n{stderr_tail}\n")


def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    registry = pd.read_csv(REGISTRY)
    all_ids = sorted(registry["short_id"].astype(str).tolist())
    total = len(all_ids)

    completed = get_completed_video_ids()
    remaining = [vid for vid in all_ids if vid not in completed]

    print(f"Total: {total} | Completed: {len(completed)} | Remaining: {len(remaining)}")
    log_message(f"Batch started — {len(remaining)} videos to process")

    succeeded = 0
    failed = 0
    batch_start = time.time()

    for n, video_id in enumerate(remaining, start=len(completed) + 1):
        log_message(f"Starting {video_id} ({n} of {total})")
        t0 = time.time()

        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.run_pipeline",
                 "--video_id", video_id,
                 "--video_dir", VIDEO_DIR],
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(PROJECT_DIR),
            )

            elapsed = round((time.time() - t0) / 60, 1)

            if result.returncode == 0:
                succeeded += 1
                log_message(f"DONE {video_id} in {elapsed} min ({n} of {total})")
            else:
                failed += 1
                stderr_tail = result.stderr[-500:] if result.stderr else "(no stderr)"
                log_error(video_id, stderr_tail)
                log_message(f"FAILED {video_id} (exit {result.returncode}) — see batch_errors.log, continuing")

        except subprocess.TimeoutExpired:
            failed += 1
            log_error(video_id, "TimeoutExpired after 3600s")
            log_message(f"FAILED {video_id} — timed out after 60 min, continuing")

        except Exception as exc:
            failed += 1
            log_error(video_id, str(exc))
            log_message(f"FAILED {video_id} — {exc}, continuing")

    total_hours = round((time.time() - batch_start) / 3600, 2)
    summary = (
        f"BATCH COMPLETE: {succeeded} succeeded, {failed} failed, "
        f"total time {total_hours} hours"
    )
    log_message(summary)
    print(summary)


if __name__ == "__main__":
    main()
