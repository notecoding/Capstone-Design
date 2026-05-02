"""
ai_engine/src/preprocess.py

영상 파일 → 프레임 추출 전담 모듈.

[v1 → v2 변경사항]
  - save_evidence_frames() 제거 → postprocess.py로 이동
    이유: 프레임 저장은 '후처리'이지 '전처리'가 아님.
         전처리 파일에 후처리 로직이 섞이면 유지보수 시 혼란 발생.

[이 파일의 역할]
  영상을 받아서 numpy 배열 형태의 프레임을 뽑아주는 것만 담당합니다.
  저장, 분석, 판정은 전혀 하지 않습니다.

함수 2개:
  extract_frames()          - CLIP/FFT용 균등 N프레임
  extract_temporal_frames() - 시공간 분석용 연속 프레임
"""

import cv2
import numpy as np
from ai_engine.src.config import VIDEO_CONFIG, TEMPORAL_CONFIG


def extract_frames(video_path: str) -> tuple[list[np.ndarray], list[float]]:
    """
    CLIP / FFT 분석용 균등 간격 프레임 추출.

    동작 방식:
      영상 전체 길이를 N등분해서 각 위치의 프레임을 하나씩 뽑습니다.
      예: 100프레임 영상에서 8개 추출 → 0, 14, 28, 42, 56, 70, 84, 98번 프레임

    이렇게 하는 이유:
      CLIP은 개별 프레임의 특징을 보는 모델입니다.
      영상 전체를 고르게 대표하는 프레임들이 필요하므로 균등 추출을 씁니다.
      연속 프레임을 쓰면 한 장면만 과대 대표될 수 있습니다.

    Args:
        video_path: 분석할 영상 파일 경로

    Returns:
        frames    : BGR numpy 배열 리스트. shape: (H, W, 3)
        timestamps: 각 프레임의 초단위 타임스탬프 (증거 프레임 저장 시 사용)

    Raises:
        ValueError: 영상을 열 수 없거나 프레임이 없을 때
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"영상을 열 수 없습니다: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if total_frames <= 0:
        cap.release()
        raise ValueError("유효한 프레임이 없습니다.")

    # max_frames와 실제 프레임 수 중 작은 것으로 추출 개수 결정
    n       = min(VIDEO_CONFIG["max_frames"], total_frames)
    indices = np.linspace(0, total_frames - 1, n, dtype=int).tolist()

    frames, timestamps = [], []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            # 모든 프레임을 동일 크기로 정규화 (모델 입력 규격 맞춤)
            resized = cv2.resize(frame, VIDEO_CONFIG["frame_size"])
            frames.append(resized)
            timestamps.append(round(idx / fps, 2))

    cap.release()
    return frames, timestamps


def extract_temporal_frames(video_path: str) -> list[list[np.ndarray]]:
    """
    시공간 분석용 연속 프레임 추출.

    동작 방식:
      균등 추출과 달리, 특정 구간에서 연속된 프레임들을 뽑습니다.
      AI 영상의 temporal artifact(시간적 불일치)는 연속 프레임을 봐야 잡힙니다.

      - 30초 이상: 앞(25%) / 뒤(75%) 두 구간 → 각 16프레임
      - 30초 미만: 중간(25%) 한 구간 → 16프레임

    두 구간을 보는 이유:
      AI 영상도 초반과 후반의 품질이 다를 수 있습니다.
      초반만 보면 후반의 artifact를 놓칠 수 있으므로
      긴 영상은 두 군데를 샘플링합니다.

    Args:
        video_path: 분석할 영상 파일 경로

    Returns:
        segments: 구간별 프레임 리스트
                  [[구간1 프레임 16개], [구간2 프레임 16개]]
                  각 프레임은 BGR numpy 배열
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

    # 영상 길이에 따라 샘플링 시작 위치 결정
    if duration_sec >= threshold_sec:
        start_indices = [
            int(total_frames * 0.25),   # 앞쪽 구간
            int(total_frames * 0.75),   # 뒤쪽 구간
        ]
    else:
        start_indices = [
            int(total_frames * 0.25),   # 중간 구간 하나만
        ]

    segments   = []
    frame_size = VIDEO_CONFIG["frame_size"]

    for start_idx in start_indices:
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

        # 최소 프레임 이상 확보된 구간만 사용
        if len(seg_frames) >= min_frames:
            segments.append(seg_frames)

    cap.release()
    return segments