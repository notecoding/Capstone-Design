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
# 기본 분석기 — 타겟 유무 관계없이 항상 실행
ANALYZERS = [
    "clip",       # DeCoF Transformer — 핵심
    "frequency",  # FFT 주파수 분석 (기존 3가지 + 심화 3가지)
    "metadata",   # 메타데이터 분석
    # "temporal", # 시공간 분석 비활성화 (Phase C에서 교체 예정)
]

# ── 앙상블 가중치 (합 = 1.0) ──────────────────────────────────────────────
# CLIP을 DeCoF 방식으로 교체했으므로 신뢰도가 높아져 가중치 상향.
# Temporal도 핵심 모듈이므로 높게 유지.
# 임계값 검증(validate_thresholds.py) 후 수치 조정 권장.
ANALYZER_WEIGHTS = {
    # 기본 분석기
    "clip":      0.60,   # DeCoF Transformer (핵심 — 2라운드 학습 완료)
    "frequency": 0.25,   # FFT 주파수 분석 심화
    "metadata":  0.15,   # 메타데이터 분석 (보조)
    "temporal":  0.00,   # 시공간 분석 (보류 — Phase C에서 교체 예정)

    # 타겟 영역 분석기 (임시: DeCoF를 영역 크롭에 적용)
    "clip_face":       0.00,   # 얼굴 타겟 — 얼굴 크롭 후 DeCoF (감지 완성, 가중치는 검증 후)
    "clip_background": 0.00,   # 배경 타겟 — 배경 마스킹 후 DeCoF (동일)

    # 타겟 고유 분석기 (Phase 완성 후 가중치 설정)
    "rppg":      0.00,   # 얼굴 타겟 — Phase B: 혈류 신호 감지
    "fft_deep":  0.00,   # 배경 타겟 — MediaPipe 배경 크롭 후 활성화 예정
    "physics":   0.00,   # 움직임 — NSG근사. benchmark 결과 앙상블 마진 감소시켜 0 유지. 점수는 기록용
    "audio":     0.00,   # 음성 타겟 — 추후 추가 예정
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
    "min_duration": 0.5,    # 0.5초 미만 → 판단 불가
                             # Crafter(1.7초), HotShot(1.0초), MoonValley(1.8초) 대응
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

# ── 물리 일관성 설정 (physics 분석기, temporal 대체) ───────────────────────────
# NSG(Normalized Spatiotemporal Gradient) 논문 원리의 경량 근사.
#   원리: 자연 영상에서 시간 변화(I_t)는 공간 구조(grad I) x 움직임(광류)으로 설명돼야 함.
#         광류 밝기보존 제약 잔차 r = I_x*u + I_y*v + I_t 가 작아야 자연스러움.
#   AI 영상: 고무판 변형/물체 출몰 등으로 움직임이 외형을 보존 못 함 → 잔차 큼.
#   정규화: |r| / (|grad I| + eps) — 텍스처 많은 영역 과대대표 방지 (NSG의 정규화 차용).
# !! threshold는 calibrate(실제 vs AI 측정) 후 교체. 현재는 임시값 !!
PHYSICS_CONFIG = {
    "max_pairs":   12,      # 분석할 연속 프레임 쌍 최대 수 (속도 제한)
    "eps":         1.0,     # 정규화 분모 안정화 (그래디언트 0 방지)
    "resid_norm":  1.064,   # 정규화 잔차를 0~1로 매핑하는 기준 (calibrate로 측정, 95퍼센타일)
    "std_weight":  0.3,     # 잔차의 시간적 변동(표준편차) 반영 비중
    # calibrate_physics 결과 AUC=0.154 → AI가 잔차 '낮음'(과도하게 매끄러운 움직임).
    # 따라서 점수 방향을 반전: 잔차 작을수록 AI 의심 점수 높게.
    "invert":      True,
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


# ── 영역 감지 설정 (region.py) ─────────────────────────────────────────────
# 얼굴/배경 크롭, 음성 VAD, 움직임 측정 파라미터.
REGION_CONFIG = {
    # 얼굴 크롭 여백 (검출 박스 대비 비율, 0.3 = 30% 확장)
    "face_margin": 0.3,

    # 배경 마스킹: 인물 픽셀을 채울 중립값 (회색 128)
    "bg_fill_value": 128,
    # MediaPipe Selfie Seg 신뢰도 임계값 (이 값 초과 = 인물)
    "seg_threshold": 0.5,

    # webrtcvad 공격성 (0~3, 높을수록 비음성 엄격 제거)
    "vad_aggressiveness": 2,
    # 음성 프레임 비율이 이 값 이상이면 has_voice = True
    "voice_ratio_threshold": 0.15,

    # 움직임 정규화 기준 (평균 광류 픽셀 이동량을 이 값으로 나눠 0~1화)
    "motion_norm": 5.0,
}
