"""
Download VIRAT ground-truth object annotation files from Kitware's public API.

For each video in video_registry.csv:
  - Extract scene ID (e.g. VIRAT_S_000205)
  - Search Kitware for <scene_id>.viratdata.objects.txt
  - Download and save to data/annotations/
"""

import csv
import os
import time
import requests

REGISTRY_CSV = os.path.join(os.path.dirname(__file__), "..", "video_registry.csv")
ANNOTATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "annotations")
KITWARE_SEARCH = "https://data.kitware.com/api/v1/resource/search"
KITWARE_DOWNLOAD = "https://data.kitware.com/api/v1/item/{item_id}/download"
REQUEST_TIMEOUT = 30  # seconds


def scene_id_from_filename(filename: str) -> str:
    """VIRAT_S_000205_02_000409_000566.mp4 -> VIRAT_S_000205"""
    stem = filename.rsplit(".", 1)[0]          # strip .mp4
    parts = stem.split("_")                    # ['VIRAT', 'S', '000205', ...]
    return "_".join(parts[:3])                 # VIRAT_S_000205


def search_item(annotation_name: str) -> str | None:
    """Return the Kitware item ID for the given annotation filename, or None."""
    params = {"q": annotation_name, "types": "item"}
    resp = requests.get(KITWARE_SEARCH, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # Response is {"item": [...], ...} — find exact name match
    items = data.get("item", [])
    for item in items:
        if item.get("name") == annotation_name:
            return item["_id"]

    # Fallback: return first result if there is only one
    if len(items) == 1:
        return items[0]["_id"]

    return None


def download_item(item_id: str, dest_path: str) -> None:
    """Stream a Kitware item download to dest_path."""
    url = KITWARE_DOWNLOAD.format(item_id=item_id)
    resp = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def load_registry(csv_path: str) -> list[str]:
    """Return list of original_filename values from video_registry.csv."""
    filenames = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filenames.append(row["original_filename"])
    return filenames


def main():
    os.makedirs(ANNOTATIONS_DIR, exist_ok=True)

    filenames = load_registry(REGISTRY_CSV)
    total = len(filenames)

    # Deduplicate scene IDs while preserving order (multiple clips share a scene)
    seen_scenes: set[str] = set()
    scene_ids: list[str] = []
    for fn in filenames:
        sid = scene_id_from_filename(fn)
        if sid not in seen_scenes:
            seen_scenes.add(sid)
            scene_ids.append(sid)

    print(f"Registry: {total} videos → {len(scene_ids)} unique scenes")
    print(f"Saving to: {os.path.abspath(ANNOTATIONS_DIR)}\n")

    downloaded = 0
    skipped = 0
    missing = 0

    for idx, scene_id in enumerate(scene_ids, start=1):
        annotation_name = f"{scene_id}.viratdata.objects.txt"
        dest_path = os.path.join(ANNOTATIONS_DIR, annotation_name)

        if os.path.exists(dest_path):
            print(f"  [{idx}/{len(scene_ids)}] Already exists — skipping {scene_id}")
            skipped += 1
            continue

        try:
            item_id = search_item(annotation_name)
            if item_id is None:
                print(f"  [{idx}/{len(scene_ids)}] NOT FOUND on Kitware: {scene_id}")
                missing += 1
                continue

            download_item(item_id, dest_path)
            size_kb = os.path.getsize(dest_path) / 1024
            print(f"  [{idx}/{len(scene_ids)}] Downloaded ({size_kb:.1f} KB): {scene_id}")
            downloaded += 1

            # Be polite to the API
            time.sleep(0.5)

        except requests.RequestException as e:
            print(f"  [{idx}/{len(scene_ids)}] ERROR for {scene_id}: {e}")
            missing += 1

    print(f"\n--- Summary ---")
    print(f"  Downloaded : {downloaded}")
    print(f"  Skipped    : {skipped} (already present)")
    print(f"  Missing/err: {missing}")
    print(f"  Total scenes: {len(scene_ids)}")


if __name__ == "__main__":
    main()
