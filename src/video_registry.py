import os
import csv
import sys
from pathlib import Path

import cv2
import pandas as pd

VIDEO_DIR = Path(r"S:\works\Video compression Research\CCTV 01")
OUTPUT_CSV = Path(r"S:\works\Video compression Research\RPCA_Hybrid_Project\video_registry.csv")
FRAME_CAP = 300
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


def scan_videos(directory: Path) -> list[Path]:
    files = [
        f for f in sorted(directory.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return files


def extract_metadata(video_path: Path) -> dict | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    duration = round(total_frames / fps, 2) if fps > 0 else 0.0
    file_size_mb = round(video_path.stat().st_size / (1024 * 1024), 2)

    return {
        "original_filename": video_path.name,
        "duration_seconds": duration,
        "total_frames": total_frames,
        "fps": round(fps, 2),
        "width": width,
        "height": height,
        "file_size_mb": file_size_mb,
    }


def build_registry() -> None:
    print(f"Scanning: {VIDEO_DIR}\n")

    video_files = scan_videos(VIDEO_DIR)
    if not video_files:
        print("No video files found.")
        sys.exit(1)

    records = []
    errors = []

    for idx, path in enumerate(video_files, start=1):
        short_id = f"video_{idx:02d}"
        meta = extract_metadata(path)
        if meta is None:
            errors.append(path.name)
            print(f"  [ERROR] Could not read: {path.name}")
            continue
        meta["short_id"] = short_id
        # reorder columns
        record = {
            "short_id": short_id,
            "original_filename": meta["original_filename"],
            "duration_seconds": meta["duration_seconds"],
            "total_frames": meta["total_frames"],
            "fps": meta["fps"],
            "width": meta["width"],
            "height": meta["height"],
            "file_size_mb": meta["file_size_mb"],
        }
        records.append(record)

    if not records:
        print("No videos could be read.")
        sys.exit(1)

    df = pd.DataFrame(records)
    df.to_csv(OUTPUT_CSV, index=False)

    # --- Console summary table ---
    col_widths = {
        "short_id": 10,
        "original_filename": 50,
        "total_frames": 13,
        "duration_seconds": 13,
        "fps": 7,
        "width": 7,
        "height": 7,
        "file_size_mb": 13,
    }
    header = (
        f"{'short_id':<10}  {'filename':<50}  {'frames':>13}  "
        f"{'duration(s)':>13}  {'fps':>7}  {'W':>7}  {'H':>7}  {'size(MB)':>13}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in records:
        print(
            f"{r['short_id']:<10}  {r['original_filename']:<50}  "
            f"{r['total_frames']:>13}  {r['duration_seconds']:>13.2f}  "
            f"{r['fps']:>7.2f}  {r['width']:>7}  {r['height']:>7}  "
            f"{r['file_size_mb']:>13.2f}"
        )
    print(sep)

    # --- Statistics ---
    total = len(records)
    under_cap = [r for r in records if r["total_frames"] < FRAME_CAP]
    shortest = min(records, key=lambda r: r["total_frames"])
    longest = max(records, key=lambda r: r["total_frames"])

    print(f"\nTotal videos found      : {total}")
    print(f"Under {FRAME_CAP} frames (adaptive) : {len(under_cap)}")
    if under_cap:
        for r in under_cap:
            print(f"  {r['short_id']}  {r['original_filename']}  ({r['total_frames']} frames)")
    print(
        f"Shortest video          : {shortest['short_id']} — "
        f"{shortest['total_frames']} frames / {shortest['duration_seconds']}s"
    )
    print(
        f"Longest video           : {longest['short_id']} — "
        f"{longest['total_frames']} frames / {longest['duration_seconds']}s"
    )
    if errors:
        print(f"\nVideos that could not be read ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
    else:
        print("\nNo read errors.")

    print(f"\nRegistry saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    build_registry()
