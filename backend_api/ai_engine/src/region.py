"""
ai_engine/src/region.py

영역 감지 + 크롭/마스크 전담 모듈.

[이 파일의 역할]
  영상에서 얼굴/배경/음성/움직임 영역을 감지하고,
  얼굴/배경 영역을 잘라낸 프레임을 만들어 줍니다.
  판별(AI 여부 점수)은 하지 않습니다. 그건 inference.py의 분석기가 합니다.

[감지 방식 — 주력 → 폴백]
  얼굴   : MediaPipe BlazeFace  → OpenCV Haar (내장, 다운로드 불필요)
  배경   : MediaPipe Selfie Seg → 얼굴 박스 기반 마스킹 폴백
  음성   : ffmpeg 오디오 추출   → webrtcvad 음성구간 감지
  움직임 : OpenCV Optical Flow (Farneback)

[설계 의도]
  주력(MediaPipe)은 모델 파일을 런타임에 한 번 받아 캐시합니다.
  네트워크가 막힌 환경에서는 자동으로 폴백으로 내려갑니다.
  어떤 환경에서도 예외로 죽지 않는 것을 우선합니다.

[크롭을 단일 대표 박스로 하는 이유]
  DeCoF는 같은 영역의 프레임 간 시간적 일관성을 봅니다.
  프레임마다 다른 위치를 크롭하면 위치 정합이 깨지므로,
  검출된 얼굴 박스들의 대표값(중앙값) 하나를 모든 프레임에 동일 적용합니다.
"""

import os
import subprocess
import wave

import cv2
import numpy as np

from ai_engine.src.config import VIDEO_CONFIG, REGION_CONFIG


# ── 모델 캐시 경로 ────────────────────────────────────────────

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "checkpoints", "region")
_MP_FACE_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
_MP_SEG_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)


def _ensure_model(url: str, filename: str):
    """모델 파일을 캐시 폴더에 한 번만 받음. 실패하면 None 반환."""
    os.makedirs(_MODEL_DIR, exist_ok=True)
    path = os.path.join(_MODEL_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    try:
        import urllib.request
        urllib.request.urlretrieve(url, path)
        return path if os.path.getsize(path) > 0 else None
    except Exception:
        return None


# ── 원본 해상도 프레임 (얼굴 감지/크롭용) ─────────────────────
# extract_frames는 CLIP 입력용으로 224x224로 줄이므로 얼굴이 작아져 감지/크롭 품질이 떨어짐.
# 감지와 크롭은 원본 해상도에서 수행한다. 같은 영상을 여러 번 읽지 않도록 단일 캐시.

_hires_cache = {"path": None, "frames": None}


def get_hires_frames(video_path: str) -> list[np.ndarray]:
    """
    extract_frames와 동일한 위치의 프레임을 원본 해상도로 추출 (리사이즈 없음).
    가장 최근 1개 영상만 캐시해서 중복 디코딩을 막는다.
    """
    if _hires_cache["path"] == video_path and _hires_cache["frames"] is not None:
        return _hires_cache["frames"]

    cap = cv2.VideoCapture(video_path)
    frames = []
    if cap.isOpened():
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total > 0:
            n = min(VIDEO_CONFIG["max_frames"], total)
            indices = np.linspace(0, total - 1, n, dtype=int).tolist()
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)  # 원본 해상도 유지
    cap.release()

    _hires_cache["path"] = video_path
    _hires_cache["frames"] = frames
    return frames


# ── 얼굴 감지기 (싱글턴) ──────────────────────────────────────

_face_detector = None      # MediaPipe Tasks FaceDetector
_haar_cascade = None       # OpenCV 폴백
_face_mode = None          # "mediapipe" | "haar" | "none"


def _get_face_detector():
    """얼굴 감지기 준비. MediaPipe 실패 시 Haar로 폴백."""
    global _face_detector, _haar_cascade, _face_mode
    if _face_mode is not None:
        return

    # 1순위: MediaPipe BlazeFace
    model_path = _ensure_model(_MP_FACE_URL, "blaze_face_short_range.tflite")
    if model_path:
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
            base = mp_python.BaseOptions(model_asset_path=model_path)
            opts = mp_vision.FaceDetectorOptions(base_options=base)
            _face_detector = mp_vision.FaceDetector.create_from_options(opts)
            _face_mode = "mediapipe"
            return
        except Exception:
            _face_detector = None

    # 폴백: OpenCV Haar (내장, 다운로드 불필요)
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _haar_cascade = cv2.CascadeClassifier(cascade_path)
        _face_mode = "haar" if not _haar_cascade.empty() else "none"
    except Exception:
        _face_mode = "none"


def _detect_face_boxes(frames: list[np.ndarray]) -> list[tuple]:
    """
    각 프레임에서 얼굴 박스를 검출해 (x, y, w, h) 픽셀 좌표 리스트로 반환.
    얼굴이 없는 프레임은 건너뜀.
    """
    _get_face_detector()
    boxes = []

    if _face_mode == "mediapipe":
        import mediapipe as mp
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = _face_detector.detect(mp_img)
            if res.detections:
                # 가장 큰 얼굴 하나만 사용
                best = max(res.detections,
                           key=lambda d: d.bounding_box.width * d.bounding_box.height)
                b = best.bounding_box
                boxes.append((b.origin_x, b.origin_y, b.width, b.height))

    elif _face_mode == "haar":
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = _haar_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            if len(faces) > 0:
                # 가장 큰 얼굴 하나
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                boxes.append((int(x), int(y), int(w), int(h)))

    return boxes


def _representative_box(boxes: list[tuple], shape: tuple) -> tuple | None:
    """
    검출된 박스들의 대표 박스(중앙값) + 여백을 적용해 반환.
    모든 프레임에 동일 적용할 단일 박스. 화면 경계로 클램프.
    """
    if not boxes:
        return None
    arr = np.array(boxes, dtype=float)
    x, y, w, h = np.median(arr, axis=0)

    margin = REGION_CONFIG["face_margin"]
    cx, cy = x + w / 2, y + h / 2
    w, h = w * (1 + margin), h * (1 + margin)
    x, y = cx - w / 2, cy - h / 2

    H, W = shape[:2]
    x = max(0, int(x)); y = max(0, int(y))
    w = min(W - x, int(w)); h = min(H - y, int(h))
    if w < 10 or h < 10:
        return None
    return (x, y, w, h)


# ── 얼굴 영역 크롭 ────────────────────────────────────────────

def crop_face(frames: list[np.ndarray], box: tuple) -> list[np.ndarray]:
    """
    단일 대표 박스로 모든 프레임을 잘라 frame_size로 정규화.
    box: (x, y, w, h). clip_face 분석기 입력용.
    """
    if box is None:
        return []
    x, y, w, h = box
    size = VIDEO_CONFIG["frame_size"]
    out = []
    for frame in frames:
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            continue
        out.append(cv2.resize(crop, size))
    return out


# ── 배경 세그멘테이션 (싱글턴) ────────────────────────────────

_segmenter = None
_seg_mode = None  # "mediapipe" | "none"


def _get_segmenter():
    global _segmenter, _seg_mode
    if _seg_mode is not None:
        return
    model_path = _ensure_model(_MP_SEG_URL, "selfie_segmenter.tflite")
    if model_path:
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
            base = mp_python.BaseOptions(model_asset_path=model_path)
            opts = mp_vision.ImageSegmenterOptions(
                base_options=base, output_confidence_masks=True
            )
            _segmenter = mp_vision.ImageSegmenter.create_from_options(opts)
            _seg_mode = "mediapipe"
            return
        except Exception:
            _segmenter = None
    _seg_mode = "none"


def mask_background(frames: list[np.ndarray], face_box: tuple | None) -> list[np.ndarray]:
    """
    인물(전경)을 중립 회색으로 가린 배경 프레임 반환.
    주력: MediaPipe Selfie Seg로 인물 마스크 → 인물 픽셀을 회색으로.
    폴백: 얼굴 박스를 아래로 확장(상반신 근사)해서 회색으로.
    인물/얼굴 둘 다 없으면 전체 프레임이 곧 배경이므로 원본 반환.
    """
    _get_segmenter()
    fill = REGION_CONFIG["bg_fill_value"]
    size = VIDEO_CONFIG["frame_size"]
    out = []

    if _seg_mode == "mediapipe":
        import mediapipe as mp
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = _segmenter.segment(mp_img)
            conf = res.confidence_masks[0].numpy_view()  # 1=인물
            person = conf > REGION_CONFIG["seg_threshold"]
            bg = frame.copy()
            bg[person] = fill
            out.append(cv2.resize(bg, size))
        return out

    # 폴백: 얼굴 박스 기반 상반신 근사 마스킹
    if face_box is not None:
        x, y, w, h = face_box
        for frame in frames:
            H, W = frame.shape[:2]
            bg = frame.copy()
            # 얼굴 아래로 3.5배까지 상반신으로 간주, 좌우 약간 확장
            x0 = max(0, int(x - w * 0.3)); x1 = min(W, int(x + w * 1.3))
            y0 = max(0, y); y1 = min(H, int(y + h * 3.5))
            bg[y0:y1, x0:x1] = fill
            out.append(cv2.resize(bg, size))
        return out

    # 인물 없음 → 전체가 배경 (단, frame_size로 정규화)
    return [cv2.resize(f, size) for f in frames]


# ── 음성 감지 (ffmpeg + webrtcvad) ────────────────────────────

def _extract_audio_pcm(video_path: str, sr: int = 16000) -> bytes | None:
    """ffmpeg로 16kHz 모노 16bit PCM 추출. 오디오 트랙 없으면 None."""
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", video_path,
            "-vn", "-ac", "1", "-ar", str(sr),
            "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        pcm = proc.stdout
        return pcm if pcm and len(pcm) > 0 else None
    except Exception:
        return None


def detect_voice(video_path: str) -> dict:
    """
    오디오 트랙 존재 + 음성 구간 비율 감지.
    반환: {has_audio, has_voice, speech_ratio}
    speech_ratio: 음성으로 판정된 30ms 프레임 비율 (0~1)
    """
    sr = 16000
    pcm = _extract_audio_pcm(video_path, sr)
    if pcm is None:
        return {"has_audio": False, "has_voice": False, "speech_ratio": 0.0}

    try:
        import webrtcvad
        vad = webrtcvad.Vad(REGION_CONFIG["vad_aggressiveness"])
        frame_ms = 30
        frame_bytes = int(sr * frame_ms / 1000) * 2  # 16bit = 2 bytes
        total = speech = 0
        for i in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
            chunk = pcm[i:i + frame_bytes]
            total += 1
            if vad.is_speech(chunk, sr):
                speech += 1
        ratio = (speech / total) if total else 0.0
        has_voice = ratio >= REGION_CONFIG["voice_ratio_threshold"]
        return {"has_audio": True, "has_voice": has_voice,
                "speech_ratio": round(ratio, 4)}
    except Exception:
        # VAD 실패해도 오디오 존재는 보고
        return {"has_audio": True, "has_voice": False, "speech_ratio": 0.0}


# ── 움직임 측정 (Optical Flow) ────────────────────────────────

def measure_motion(frames: list[np.ndarray]) -> float:
    """
    연속 프레임 간 광류 크기 평균으로 움직임 수준 산출 (0~1 정규화).
    motion 타겟은 두기로 했으나 분석은 base clip(DeCoF)이 담당.
    여기서는 '움직임 양' 측정만 한다.
    """
    if len(frames) < 2:
        return 0.0
    mags = []
    prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    for f in frames[1:]:
        cur = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(
            prev, cur, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        mags.append(float(mag.mean()))
        prev = cur
    avg = float(np.mean(mags)) if mags else 0.0
    # 경험적 정규화 (픽셀 이동량 기준)
    return float(np.clip(avg / REGION_CONFIG["motion_norm"], 0.0, 1.0))


# ── 통합 감지 ─────────────────────────────────────────────────

def detect_regions(video_path: str, frames: list[np.ndarray]) -> dict:
    """
    영상의 영역 정보를 한 번에 감지.
    inference.py의 _detect_video_type가 이 함수를 호출한다.

    반환:
      has_face, face_box        : 얼굴 존재 여부 + 대표 박스(x,y,w,h)
      has_audio, has_voice, speech_ratio
      motion_level              : 0~1
      face_mode, seg_mode       : 어떤 감지기가 쓰였는지 (디버그/리포트용)
    [감지 해상도]
      얼굴 감지/크롭/배경 마스킹은 원본 해상도 프레임에서 수행 (품질 유지).
      움직임은 전달받은 224 프레임으로 측정 (속도, 크기 추정엔 충분).
    """
    hires = get_hires_frames(video_path)
    boxes = _detect_face_boxes(hires)
    face_box = _representative_box(boxes, hires[0].shape) if hires else None
    has_face = face_box is not None

    voice = detect_voice(video_path)
    motion_level = measure_motion(frames)

    # 세그멘터 가용 여부를 미리 확정 (탐지 보고용 — 실제 마스킹은 분석 시 수행)
    _get_segmenter()

    return {
        "has_face":     has_face,
        "face_box":     face_box,
        "has_audio":    voice["has_audio"],
        "has_voice":    voice["has_voice"],
        "speech_ratio": voice["speech_ratio"],
        "motion_level": round(motion_level, 4),
        "face_mode":    _face_mode or "none",
        "seg_mode":     _seg_mode or "none",
    }
