"""
ai_engine/src/config.py

모든 설정값이 여기에 있습니다.
점수가 이상하면 여기 값을 조정하세요.

[변경 이력]
  v1 → v2: CLIP Zero-shot 프롬프트 제거, DeCoF 방식으로 교체
            AnalyzerResult dataclass 추가 (base.py 연동)
            ANALYZERS registry 추가
            video_type 플래그 추가
            reliability 임계값 추가
"""

# ── 활성화할 분석기 목록 (Registry) ───────────────────────────────────────
# 여기에 이름을 추가하는 것만으로 새 분석기가 파이프라인에 포함됩니다.
# 나중에 rppg, physics, cnn_detect 등을 추가할 때 이 목록에만 넣으면 됩니다.
ANALYZERS = [
    "clip",
    "frequency",
    "metadata",
    "temporal",
    # "rppg",        # Phase B: 얼굴 영상 생체 신호 (미래)
    # "physics",     # Phase C: 물리 일관성 체크 (미래)
    # "cnn_detect",  # Phase A: 주파수 심화 (미래)
]

# ── 앙상블 가중치 (합 = 1.0) ──────────────────────────────────────────────
# CLIP을 DeCoF 방식으로 교체했으므로 신뢰도가 높아져 가중치 상향.
# Temporal도 핵심 모듈이므로 높게 유지.
# 임계값 검증(validate_thresholds.py) 후 수치 조정 권장.
ANALYZER_WEIGHTS = {
    "clip":      0.45,   # DeCoF 방식 프레임 간 불일치 (핵심)
    "temporal":  0.35,   # 시공간 분석 (핵심)
    "frequency": 0.15,   # FFT 주파수 분석 (보조)
    "metadata":  0.05,   # 메타데이터 분석 (보조)
}

# ── is_ai 판정 임계값 ──────────────────────────────────────────────────────
# confidence가 이 값 이상이면 is_ai = True
AI_THRESHOLD = 0.50

# ── risk_level 기준 ────────────────────────────────────────────────────────
RISK_THRESHOLDS = {
    "HIGH":   0.70,   # 70% 이상 → HIGH (AI 생성으로 판단)
    "MEDIUM": 0.45,   # 45~70%  → MEDIUM (가능성 있음)
                      # 45% 미만 → LOW (실제 영상으로 판단)
}

# ── reliability 기준 ──────────────────────────────────────────────────────
# confidence가 이 범위 안이면 모델이 확신하지 못하는 경계 케이스
# 프론트에서 "판단이 불확실합니다" 메시지를 띄울 때 사용
RELIABILITY_UNCERTAIN_RANGE = (0.45, 0.55)

# ── 영상 전처리 (CLIP/FFT용 균등 프레임) ──────────────────────────────────
VIDEO_CONFIG = {
    "max_frames":  8,
    "frame_size": (224, 224),
    "supported_formats": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    # 영상 길이 제한 (초 단위)
    "min_duration": 2.0,    # 2초 미만 → 판단 불가 (프레임 부족)
    "max_duration": 600.0,  # 10분 초과 → 처리 거부
}

# ── 시공간 분석 설정 ───────────────────────────────────────────────────────
TEMPORAL_CONFIG = {
    "frames_per_segment": 16,
    "long_video_threshold": 30,
    "min_frames": 4,

    # 광류 분석 지표 가중치 (합 = 1.0)
    "flow_weights": {
        "magnitude_inconsistency": 0.40,
        "direction_inconsistency": 0.20,
        "frame_difference":        0.20,
        "texture_consistency":     0.10,
        "edge_consistency":        0.10,
    },

    # !! 아래 임계값은 validate_thresholds.py 실행 후 반드시 교체하세요 !!
    # 현재는 임시값 — 실제 AI 영상 / 실제 영상으로 측정한 값이 아닙니다.
    "magnitude_threshold":  5.0,
    "direction_threshold":  0.3,
    "diff_threshold":       10.0,
    "texture_threshold":    0.15,
    "edge_threshold":       0.20,
}

# ── CLIP 설정 (DeCoF 방식) ─────────────────────────────────────────────────
# v1에서 사용하던 ai_prompts / real_prompts 제거.
# DeCoF 방식은 텍스트 없이 프레임 간 임베딩 유사도만 사용합니다.
CLIP_CONFIG = {
    "model_name": "ViT-L-14",    # v1: ViT-B-32 → v2: ViT-L-14 (정확도 향상)
    "pretrained": "openai",
    "device":     "cpu",         # GPU 있으면 "cuda"로 변경
    # 프레임 간 cosine similarity가 이 값 미만이면 AI 의심 구간
    # validate_thresholds.py 실행 후 조정 권장
    "similarity_threshold": 0.90,
}

# ── 메타데이터 분석 ────────────────────────────────────────────────────────
METADATA_CONFIG = {
    # 인코더 문자열에 이 키워드가 있으면 AI 생성 의심
    "suspicious_encoders": [
        "runway", "sora", "pika", "stable", "animatediff",
        "deforum", "gen-2", "kling", "cogvideo", "zeroscope",
        "modelscope", "videocrafter", "lavie",
    ],
    # AI 생성 모델의 표준 출력 해상도 (width, height)
    # 이 해상도와 일치하면 AI 생성 의심
    "ai_resolutions": {
        (512, 512), (768, 512), (512, 768),
        (1024, 576), (576, 1024), (1280, 720),
        (720, 1280), (1920, 1080),  # 일부 모델 출력
    },
}

# ── FFT 분석 ───────────────────────────────────────────────────────────────
# !! high_freq_threshold는 validate_thresholds.py 후 조정 필요 !!
FREQUENCY_CONFIG = {
    "high_freq_threshold": 0.75,
}