"""
ai_engine/src/preprocess.py
영상 파일 → 프레임 추출

함수 2개:
  extract_frames()          - CLIP/FFT용 균등 8프레임 (기존)
  extract_temporal_frames() - 시공간 분석용 연속 프레임 (신규 v2)
"""
import os
import cv2
import numpy as np
from pathlib import Path
from ai_engine.src.config import VIDEO_CONFIG, TEMPORAL_CONFIG


def extract_frames(video_path: str) -> tuple[list[np.ndarray], list[float]]:
    """
    [기존 함수 - CLIP/FFT용]
    영상에서 균등 간격으로 N개 프레임을 추출합니다.

    Returns:
        frames     : BGR numpy 배열 리스트
        timestamps : 각 프레임의 초단위 타임스탬프
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


def extract_temporal_frames(video_path: str) -> list[list[np.ndarray]]:
    """
    [신규 함수 v2 - 시공간 분석용]
    영상 길이에 따라 구간을 나눠서 각 구간에서 연속 프레임을 추출합니다.

    동작 방식:
      - 30초 이상: 앞/뒤 2구간에서 각각 연속 16프레임
      - 30초 미만: 중간 1구간에서 연속 16프레임
      - 프레임 수가 부족하면 자동으로 줄임

    Returns:
        segments: 구간별 프레임 리스트
                  [[구간1 프레임들], [구간2 프레임들], ...]
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"영상을 열 수 없습니다: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration_sec = total_frames / fps

    frames_per_seg = TEMPORAL_CONFIG["frames_per_segment"]
    min_frames     = TEMPORAL_CONFIG["min_frames"]
    threshold_sec  = TEMPORAL_CONFIG["long_video_threshold"]

    # ── 구간 시작 프레임 인덱스 결정 ──────────────────────────────────────
    if duration_sec >= threshold_sec:
        # 30초 이상: 앞(25%) / 뒤(75%) 두 지점
        start_indices = [
            int(total_frames * 0.25),
            int(total_frames * 0.75),
        ]
    else:
        # 30초 미만: 중간(25%) 한 지점
        start_indices = [
            int(total_frames * 0.25),
        ]

    # ── 각 구간에서 연속 프레임 추출 ──────────────────────────────────────
    segments = []
    frame_size = VIDEO_CONFIG["frame_size"]

    for start_idx in start_indices:
        # 실제 뽑을 프레임 수 계산 (영상 끝을 넘지 않게)
        available = total_frames - start_idx
        n_frames  = min(frames_per_seg, max(available, min_frames))
        n_frames  = max(n_frames, min_frames)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_idx)
        seg_frames = []

        for _ in range(n_frames):
            ret, frame = cap.read()
            if not ret:
                break
            resized = cv2.resize(frame, frame_size)
            seg_frames.append(resized)

        if len(seg_frames) >= min_frames:
            segments.append(seg_frames)

    cap.release()
    return segments


def save_evidence_frames(
    video_path: str,
    output_dir: str,
    timestamps: list[float],
    top_n: int = 3,
) -> list[dict]:
    """
    evidence 프레임을 output_dir에 저장합니다.
    파일명 규칙: frame_{초단위}.jpg  (예: frame_5.2.jpg)

    Returns:
        [{"timestamp": 5.2, "file_name": "frame_5.2.jpg"}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)

    cap          = cv2.VideoCapture(video_path)
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
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