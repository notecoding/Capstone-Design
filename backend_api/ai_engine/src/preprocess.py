"""
ai_engine/src/preprocess.py
영상 파일 → 프레임 리스트 추출 + evidence 프레임 저장

담당: AI 파트
"""
import os
import cv2
import numpy as np
from pathlib import Path
from ai_engine.src.config import VIDEO_CONFIG


def extract_frames(video_path: str) -> tuple[list[np.ndarray], list[float]]:
    """
    영상에서 균등 간격으로 N개 프레임을 추출합니다.

    Returns:
        frames      : BGR numpy 배열 리스트 (H x W x 3)
        timestamps  : 각 프레임의 초단위 타임스탬프 리스트
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"영상을 열 수 없습니다: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if total_frames <= 0:
        cap.release()
        raise ValueError("유효한 프레임이 없습니다.")

    n       = min(VIDEO_CONFIG["max_frames"], total_frames)
    indices = np.linspace(0, total_frames - 1, n, dtype=int).tolist()

    frames, timestamps = [], []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            resized = cv2.resize(frame, VIDEO_CONFIG["frame_size"])
            frames.append(resized)
            timestamps.append(round(idx / fps, 2))

    cap.release()
    return frames, timestamps


def save_evidence_frames(
    video_path: str,
    output_dir: str,
    timestamps: list[float],
    top_n: int = 3,
) -> list[dict]:
    """
    evidence 프레임을 output_dir에 저장합니다.
    파일명 규칙: frame_{초단위}.jpg  (예: frame_5.2.jpg)

    Args:
        video_path : 원본 영상 경로
        output_dir : 저장 폴더 (백엔드가 지정해 줌)
        timestamps : 저장할 프레임의 타임스탬프 리스트
        top_n      : 저장할 최대 프레임 수

    Returns:
        [{"timestamp": 5.2, "file_name": "frame_5.2.jpg"}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    evidence = []
    for ts in timestamps[:top_n]:
        frame_idx = min(int(ts * fps), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        file_name = f"frame_{ts}.jpg"
        save_path  = os.path.join(output_dir, file_name)
        cv2.imwrite(save_path, frame)
        evidence.append({"timestamp": ts, "file_name": file_name})

    cap.release()
    return evidence
