from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def load_video_frames(video_path, max_frames=300):
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n_frames = min(max_frames, total_frames)

    frames = []
    for _ in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
        frames.append(resized.astype(np.float64) / 255.0)

    cap.release()

    result = np.array(frames, dtype=np.float64)  # (T, 180, 320)
    print(f"Loaded {len(frames)} frames from {video_path.name} — shape: {result.shape}")
    return result


def frames_to_matrix(frames):
    T, H, W = frames.shape
    return frames.reshape(H * W, T).astype(np.float64)  # (57600, T)


def frames_to_tensor(frames):
    return np.transpose(frames, (1, 2, 0)).astype(np.float64)  # (H, W, T)


def save_frames(frames, output_path):
    output_path = Path(output_path)
    np.save(output_path, frames)
    print(f"Saved frames to {output_path}")


def load_registry(registry_path):
    return pd.read_csv(registry_path)


if __name__ == "__main__":
    REGISTRY = Path(r"S:\works\Video compression Research\RPCA_Hybrid_Project\video_registry.csv")
    VIDEO_DIR = Path(r"S:\works\Video compression Research\CCTV 01")

    df = load_registry(REGISTRY)
    first = df.iloc[0]
    video_path = VIDEO_DIR / first["original_filename"]

    frames = load_video_frames(video_path, max_frames=300)
    matrix = frames_to_matrix(frames)
    tensor = frames_to_tensor(frames)

    print(f"frames shape : {frames.shape}")
    print(f"matrix shape : {matrix.shape}")
    print(f"tensor shape : {tensor.shape}")

    assert matrix.shape == (57600, 300), f"Unexpected matrix shape: {matrix.shape}"
    assert tensor.shape == (180, 320, 300), f"Unexpected tensor shape: {tensor.shape}"
    print("All shape assertions passed.")
