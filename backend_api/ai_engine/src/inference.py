"""
ai_engine/src/inference.py

백엔드가 호출하는 진입점.

[함수명/인자명은 백엔드와의 약속 — 변경 금지]
  run_ai_video_analysis(video_path: str, output_dir: str)

[v1 → v2 변경사항]
  CLIP 분석기:
    - Zero-shot 텍스트 비교 방식 완전 제거
    - DeCoF 방식으로 교체: 프레임 간 임베딩 cosine similarity 분산 측정
    - 모델: ViT-B-32 → ViT-L-14 (정확도 향상)

  반환값:
    - risk_level 추가 (기존에 계산만 하고 반환 안 했음)
    - reliability 추가 (경계 케이스 경고)
    - module_scores 추가 (프론트 근거 시각화용)

  구조:
    - AnalyzerResult 표준 인터페이스 적용
    - ANALYZERS registry 기반 분석기 실행
    - video_type 플래그 추가 (미래 분기용 뼈대)
    - save_evidence_frames → postprocess.py로 이동
    - _build_description → postprocess.py로 이동
    - _risk_level → postprocess.py로 이동

[분석기 추가 방법]
  1. config.py의 ANALYZERS 목록에 이름 추가
  2. config.py의 ANALYZER_WEIGHTS에 가중치 추가
  3. 이 파일에 _analyze_XXX() 함수 작성 (AnalyzerResult 반환)
  4. ANALYZER_MAP 딕셔너리에 등록
  → inference.py의 나머지 코드는 수정 불필요
"""

import os
import subprocess
import json
import traceback
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn

from ai_engine.src.base import AnalyzerResult
from ai_engine.src.config import (
    ANALYZERS, ANALYZER_WEIGHTS,
    AI_THRESHOLD, RISK_THRESHOLDS,
    CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG,
    VIDEO_CONFIG, TEMPORAL_CONFIG,
)
from ai_engine.src.preprocess import (
    extract_frames,
    extract_temporal_frames,
)
from ai_engine.src.postprocess import (
    save_evidence_frames,
    build_result_json,
)


# ════════════════════════════════════════════════════════
#  영상 타입 판별 (미래 분기용 뼈대)
# ════════════════════════════════════════════════════════

def _detect_video_type(video_path: str, frames: list[np.ndarray]) -> dict:
    """
    영상의 특성을 파악해서 분기 플래그를 반환합니다.

    [현재 상태]
      모든 플래그가 False로 고정되어 있습니다.
      나중에 얼굴 감지기(RetinaFace 등)를 붙일 때 has_face를 채웁니다.

    [미래에 이 플래그가 쓰이는 곳]
      has_face = True  → rPPG 분석기 활성화 (Phase B)
      has_face = False → 물리 일관성 분석기 활성화 (Phase C)
      is_short  = True → temporal 분석 skip (프레임 부족)

    Returns:
        {
          "has_face":      bool,  # 얼굴이 있는 영상인가
          "is_short":      bool,  # 3초 미만의 짧은 영상인가
          "is_compressed": bool,  # 심하게 재압축된 영상인가
        }
    """
    return {
        "has_face":      False,   # 나중에 RetinaFace 연결
        "is_short":      False,   # 나중에 duration 기반으로 채움
        "is_compressed": False,   # 나중에 품질 측정 기반으로 채움
    }


# ════════════════════════════════════════════════════════
#  입력 검증
# ════════════════════════════════════════════════════════

def _validate_video(video_path: str) -> tuple[str, str]:
    """
    영상 파일의 기본 유효성을 검사합니다.

    분석을 시작하기 전에 처리 불가능한 케이스를 걸러냅니다.
    이렇게 하면 분석기가 빈 프레임이나 너무 짧은 영상을 받는 상황을 방지합니다.

    Returns:
        ("OK", "")           → 정상
        ("REJECT", "이유")   → 분석 중단, error 반환
        ("WARN", "이유")     → 분석 진행하되, reliability에 영향

    현재 체크 항목:
      - 파일 존재 여부
      - 지원 포맷 여부
      - 영상 길이 (너무 짧거나 너무 긺)
    """
    if not os.path.exists(video_path):
        return "REJECT", f"파일 없음: {video_path}"

    ext = Path(video_path).suffix.lower()
    if ext not in VIDEO_CONFIG["supported_formats"]:
        return "REJECT", f"지원하지 않는 형식: {ext}"

    # 영상 길이 체크
    cap      = cv2.VideoCapture(video_path)
    fps      = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = n_frames / fps if fps > 0 else 0

    if duration < VIDEO_CONFIG["min_duration"]:
        return "REJECT", f"영상이 너무 짧음 ({duration:.1f}초 — 최소 {VIDEO_CONFIG['min_duration']}초 필요)"
    if duration > VIDEO_CONFIG["max_duration"]:
        return "REJECT", f"영상이 너무 긺 ({duration:.0f}초 — 최대 {VIDEO_CONFIG['max_duration']}초)"

    return "OK", ""


# ════════════════════════════════════════════════════════
#  분류 헤드 (DeCoF 완전 구조)
# ════════════════════════════════════════════════════════

_classifier = None

# ── 학습 코드(colab_train.py)의 CLIPClassifier와 완전히 동일한 구조 ──
# 구조가 다르면 load_state_dict가 실패하므로 반드시 동일하게 유지
import torch
import torch.nn as nn

class _DeCoFClassifier(nn.Module):
    """
    colab_train.py의 CLIPClassifier와 동일한 구조.
    변경 시 학습 코드도 같이 변경해야 함.

    학습 코드와의 대응:
      pos_embed  → 위치 인코딩 (n_frames=8 고정)
      transformer → 2레이어, 8헤드
      mlp        → Sigmoid 없음 (BCEWithLogitsLoss로 학습)
                   추론 시에는 torch.sigmoid()로 수동 변환
    """
    def __init__(self, feat_dim=768, n_frames=8):
        super().__init__()
        self.pos_embed = nn.Parameter(
            torch.randn(1, n_frames, feat_dim) * 0.02
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=feat_dim,
            nhead=8,
            dim_feedforward=2048,
            dropout=0.05,   # 학습 코드와 동일
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer, num_layers=2
        )
        self.mlp = nn.Sequential(
            nn.Linear(feat_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.05),  # 학습 코드와 동일
            nn.Linear(256, 1),
            # Sigmoid 없음 — BCEWithLogitsLoss로 학습한 가중치
            # 추론 시 torch.sigmoid()로 변환
        )

    def forward(self, x):
        x = x + self.pos_embed
        x = self.transformer(x)
        return self.mlp(x.mean(dim=1))


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return

    checkpoint_path = "ai_engine/checkpoints/checkpoint_main.pth"
    if not os.path.exists(checkpoint_path):
        return

    _classifier = _DeCoFClassifier(feat_dim=768, n_frames=8)
    _classifier.load_state_dict(
        torch.load(checkpoint_path, map_location="cpu")
    )
    _classifier.eval()


# ════════════════════════════════════════════════════════
#  CLIP 모델 싱글턴
# ════════════════════════════════════════════════════════

_clip_model      = None
_clip_preprocess = None

def _load_clip():
    """
    CLIP 모델을 한 번만 로드하고 재사용합니다. (싱글턴 패턴)

    왜 싱글턴인가:
      CLIP ViT-L-14는 모델 크기가 약 890MB입니다.
      요청마다 새로 로드하면 처리 시간이 수십 초씩 낭비됩니다.
      서버 프로세스가 살아있는 동안 한 번만 로드하고 계속 씁니다.

    v2 변경:
      v1에서 텍스트 인코딩(_ai_text_feats, _real_text_feats)을 여기서 했지만
      DeCoF 방식은 텍스트를 사용하지 않으므로 이미지 인코더만 로드합니다.
    """
    global _clip_model, _clip_preprocess

    if _clip_model is not None:
        return  # 이미 로드됨, 재사용

    import open_clip

    device = CLIP_CONFIG["device"]
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        CLIP_CONFIG["model_name"],   # ViT-L-14
        pretrained=CLIP_CONFIG["pretrained"],
        device=device,
    )
    _clip_model.eval()  # 추론 모드 고정 (드롭아웃 비활성화)


# ════════════════════════════════════════════════════════
#  분석기 1: CLIP (DeCoF 방식)
# ════════════════════════════════════════════════════════

def _analyze_clip(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    """
    DeCoF 완전 구조: 프레임 벡터 시퀀스를 Transformer에 입력해서 AI 판별.

    [구조]
      ViT-L/14 → 프레임 벡터 시퀀스 (1, 8, 768)
               → Transformer 2레이어
               → MLP 헤드
               → AI 확률

    [학습 전 fallback]
      checkpoint_main.pth 없으면 유사도 기반으로 동작.
      학습 후에는 Transformer 헤드가 판단.
    """
    _load_clip()
    device = CLIP_CONFIG["device"]

    # 각 프레임을 768차원 벡터로 변환
    frame_feats = []
    for frame in frames:
        rgb     = frame[:, :, ::-1]
        pil_img = Image.fromarray(rgb.astype(np.uint8))
        tensor  = _clip_preprocess(pil_img).unsqueeze(0).to(device)
        with torch.no_grad():
            feat = _clip_model.encode_image(tensor)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        frame_feats.append(feat)

    if len(frame_feats) < 2:
        return AnalyzerResult(
            score=0.5, status="skip",
            reason="CLIP: 프레임 수 부족 (2개 미만)",
        )

    # 유사도 계산 (fallback 및 detail용)
    similarities = []
    for i in range(len(frame_feats) - 1):
        sim = (frame_feats[i] @ frame_feats[i+1].T).item()
        similarities.append(sim)
    avg_sim = float(np.mean(similarities))
    std_sim = float(np.std(similarities))

    # DeCoF 완전 구조: 프레임 벡터 시퀀스를 Transformer에 입력
    _load_classifier()
    if _classifier is not None:
        feat_seq = torch.cat(frame_feats, dim=0).unsqueeze(0)  # (1, 8, 768)
        with torch.no_grad():
            logit = _classifier(feat_seq)
            # BCEWithLogitsLoss로 학습했으므로 sigmoid 수동 적용
            score = float(torch.sigmoid(logit).item())
        reason = f"CLIP(DeCoF Transformer): AI 확률 {score:.3f}"
        used_classifier = True
    else:
        # 학습 전 fallback: 유사도 기반
        # AI 영상은 flickering으로 프레임 간 유사도가 낮음
        # 실제 영상은 물리 카메라 연속성으로 유사도가 높음
        score  = float(np.clip(1.0 - avg_sim, 0.0, 1.0))
        reason = f"CLIP(fallback): 프레임 간 평균 유사도 {avg_sim:.3f} (낮을수록 AI 의심)"
        used_classifier = False

    return AnalyzerResult(
        score=score,
        status="ok",
        reason=reason,
        detail={
            "avg_similarity":    avg_sim,
            "std_similarity":    std_sim,
            "similarities":      similarities,
            "n_frames_analyzed": len(frame_feats),
            "used_classifier":   used_classifier,
        },
    )


# ════════════════════════════════════════════════════════
#  분석기 2: FFT 주파수 분석
# ════════════════════════════════════════════════════════

def _analyze_frequency(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    """
    주파수 도메인에서 AI 생성 흔적을 탐지합니다.

    [원리]
      이미지를 FFT(고속 푸리에 변환)로 주파수 도메인으로 변환하면
      GAN이나 Diffusion 모델이 생성한 이미지에서 특유의 패턴이 나타납니다.
        - 고주파 비율: AI 생성은 자연 이미지와 다른 고주파 분포를 가짐
        - 방사 분산: 주파수 에너지가 방사 방향으로 균일하지 않음
        - 방향 비대칭: 수평/수직 주파수 에너지의 불균형

    [현재 한계]
      스코어 계산이 아직 데이터 기반이 아닙니다.
      validate_thresholds.py 실행 후 high_freq_threshold를 수정해야
      신뢰할 수 있는 점수가 나옵니다.

    Args:
        frames: preprocess.extract_frames()로 추출한 프레임 리스트

    Returns:
        AnalyzerResult
          detail: 고주파비율, 방사분산, 방향비대칭 수치
    """
    threshold = FREQUENCY_CONFIG["high_freq_threshold"]
    all_hf, all_rv, all_da = [], [], []

    for frame in frames:
        # BGR → 그레이스케일 (주파수 분석은 단채널로 충분)
        gray      = np.mean(frame, axis=2)
        fft_shift = np.fft.fftshift(np.fft.fft2(gray))
        # log 스케일로 변환 (큰 값과 작은 값의 범위를 좁힘)
        mag       = np.log1p(np.abs(fft_shift))
        h, w      = mag.shape
        cx, cy    = w // 2, h // 2

        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        r    = min(h, w) // 4

        # 고주파 비율: 전체 에너지 중 외곽(고주파) 영역의 비율
        lo = mag[dist <= r].sum()
        hi = mag[dist >  r].sum()
        all_hf.append(hi / (lo + hi + 1e-8))

        # 방사 분산: 거리별 평균 에너지의 분산 (균일하지 않을수록 이상)
        profile = []
        for rr in range(1, min(cx, cy)):
            mask = (dist >= rr - 0.5) & (dist < rr + 0.5)
            if mask.sum() > 0:
                profile.append(mag[mask].mean())
        arr = np.array(profile)
        all_rv.append(float(np.var(arr) / (np.mean(arr) + 1e-8)))

        # 방향 비대칭: 수평/수직 에너지 불균형
        he = mag[cy - 2:cy + 2, :].sum()
        ve = mag[:, cx - 2:cx + 2].sum()
        all_da.append(abs(he - ve) / (he + ve + 1e-8))

    avg_hf = float(np.mean(all_hf))
    avg_rv = float(np.mean(all_rv))
    avg_da = float(np.mean(all_da))

    # !! 이 스코어 계산은 임시 방식 !!
    # validate_thresholds.py로 실제 분포를 측정한 후 교체 필요
    hf_score = max(0.0, min(1.0, 1.0 - abs(avg_hf - threshold) / threshold))
    rv_score = min(1.0, avg_rv / 5.0)
    da_score = min(1.0, avg_da * 3.0)
    score    = hf_score * 0.4 + rv_score * 0.4 + da_score * 0.2

    return AnalyzerResult(
        score=float(score),
        status="ok",
        reason=f"FFT: 고주파비={avg_hf:.3f}, 방사분산={avg_rv:.3f}, 방향비대칭={avg_da:.3f}",
        detail={
            "high_freq_ratio":    avg_hf,
            "radial_variance":    avg_rv,
            "directional_asymm":  avg_da,
        },
    )


# ════════════════════════════════════════════════════════
#  분석기 3: 메타데이터
# ════════════════════════════════════════════════════════

def _analyze_metadata(video_path: str, **kwargs) -> AnalyzerResult:
    """
    영상 파일의 메타데이터에서 AI 생성 흔적을 탐지합니다.

    [원리]
      영상 파일 안에는 인코더 이름, 해상도, C2PA 마커 등이 저장됩니다.
      AI 생성 도구들은 특유의 인코더 이름을 남기거나,
      모델 출력 해상도(512x512 등)를 그대로 유지하는 경우가 많습니다.

    [탐지 항목]
      1. 의심 인코더 키워드 (runway, sora, kling 등)
      2. C2PA 마커 (AI 생성 콘텐츠 표준 메타데이터)
      3. AI 생성 모델 표준 출력 해상도

    [강점과 한계]
      강점: ffprobe만 쓰므로 매우 빠름 (~0.1초)
      한계: 메타데이터를 지운 영상에는 무력.
            재압축하거나 SNS에서 다운받은 영상은 메타데이터가 지워질 수 있음.

    Args:
        video_path: 분석할 영상 파일 경로

    Returns:
        AnalyzerResult
          score : 탐지된 항목 수에 따라 0.2~0.95
          detail: 탐지된 메타데이터 항목 목록
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path,
            ],
            capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="ignore",
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except Exception as e:
        return AnalyzerResult(
            score=0.5, status="error",
            reason=f"ffprobe 실패: {e}",
        )

    if not data:
        return AnalyzerResult(
            score=0.5, status="skip",
            reason="메타데이터 없음",
        )

    fmt     = data.get("format", {})
    streams = data.get("streams", [])
    tags    = fmt.get("tags", {})

    components = []
    found_items = []

    # 체크 1: 의심 인코더 키워드
    encoder_str = " ".join([
        tags.get("encoder",     ""),
        tags.get("comment",     ""),
        tags.get("description", ""),
        fmt.get("format_long_name", ""),
    ]).lower()
    found_kw = [kw for kw in METADATA_CONFIG["suspicious_encoders"] if kw in encoder_str]
    if found_kw:
        components.append(0.95)
        found_items.append(f"의심 인코더: {found_kw}")
    else:
        components.append(0.20)

    # 체크 2: C2PA 마커 (AI 생성 콘텐츠 국제 표준)
    if any("c2pa" in str(v).lower() for v in tags.values()):
        components.append(0.90)
        found_items.append("C2PA AI 생성 마커 감지")
    else:
        components.append(0.25)

    # 체크 3: AI 생성 모델 표준 출력 해상도
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if video_streams:
        w = video_streams[0].get("width", 0)
        h = video_streams[0].get("height", 0)
        if (w, h) in METADATA_CONFIG["ai_resolutions"]:
            components.append(0.75)
            found_items.append(f"AI 전형 해상도: {w}x{h}")
        else:
            components.append(0.20)

    score  = float(np.mean(components)) if components else 0.5
    reason = " | ".join(found_items) if found_items else "메타데이터 이상 없음"

    return AnalyzerResult(
        score=score,
        status="ok",
        reason=reason,
        detail={"found_items": found_items},
    )


# ════════════════════════════════════════════════════════
#  분석기 4: 시공간 분석
# ════════════════════════════════════════════════════════

def _compute_optical_flow(f1: np.ndarray, f2: np.ndarray) -> np.ndarray:
    """
    두 연속 프레임 사이의 광류(Optical Flow)를 계산합니다.

    광류란 프레임 간 각 픽셀의 이동 방향과 속도를 나타내는 벡터 필드입니다.
    Farneback 알고리즘은 전체 영역의 밀집 광류를 계산합니다.

    Returns:
        flow: shape (H, W, 2) — 각 픽셀의 (x방향, y방향) 이동량
    """
    g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(
        g1, g2, None,
        pyr_scale=0.5,   # 피라미드 스케일
        levels=3,        # 피라미드 레벨 수
        winsize=15,      # 윈도우 크기
        iterations=3,    # 반복 횟수
        poly_n=5,        # 다항식 이웃 크기
        poly_sigma=1.2,  # 가우시안 표준편차
        flags=0,
    )


def _score_magnitude_inconsistency(flows: list[np.ndarray]) -> float:
    """
    지표 1: 광류 이동량 불일치
    AI 영상은 프레임 간 이동량이 갑자기 튀는 경우가 많습니다.
    이동량의 표준편차가 클수록 AI 의심.
    """
    mags = [np.sqrt(f[..., 0]**2 + f[..., 1]**2).mean() for f in flows]
    if len(mags) < 2:
        return 0.5
    return float(min(1.0, np.std(mags) / TEMPORAL_CONFIG["magnitude_threshold"]))


def _score_direction_inconsistency(flows: list[np.ndarray]) -> float:
    """
    지표 2: 광류 방향 불일치
    AI 영상은 움직임 방향이 프레임마다 갑자기 바뀌는 경우가 있습니다.
    """
    angles = [np.arctan2(f[..., 1], f[..., 0]).mean() for f in flows]
    if len(angles) < 2:
        return 0.5
    diffs    = [abs(angles[i+1] - angles[i]) for i in range(len(angles)-1)]
    avg_diff = float(np.mean(diffs))
    return float(min(1.0, avg_diff / (TEMPORAL_CONFIG["direction_threshold"] * np.pi)))


def _score_frame_difference(frames: list[np.ndarray]) -> float:
    """
    지표 3: 프레임 차분
    AI 영상은 배경이 미묘하게 변하는 패턴이 있습니다.
    인접 프레임의 픽셀 차이 편차가 클수록 AI 의심.
    """
    diffs = [
        np.abs(frames[i].astype(float) - frames[i+1].astype(float)).mean()
        for i in range(len(frames)-1)
    ]
    if not diffs:
        return 0.5
    return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["diff_threshold"]))


def _score_texture_consistency(frames: list[np.ndarray]) -> float:
    """
    지표 4: 텍스처 일관성 (LBP 기반)
    AI 영상은 머리카락, 손가락 같은 세밀한 텍스처가 프레임마다 달라집니다.
    LBP(Local Binary Pattern) 히스토그램의 프레임 간 차이가 클수록 AI 의심.

    LBP란: 각 픽셀 주변의 밝기 패턴을 이진수로 인코딩한 텍스처 기술자.
    """
    def lbp_histogram(frame: np.ndarray) -> np.ndarray:
        gray     = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        n_points = 8
        lbp      = np.zeros_like(gray, dtype=np.uint8)
        for i in range(n_points):
            angle   = 2 * np.pi * i / n_points
            dx, dy  = int(round(np.cos(angle))), int(round(np.sin(angle)))
            shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
            lbp    += (shifted >= gray).astype(np.uint8) * (2 ** i)
        hist, _  = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist     = hist.astype(float)
        hist    /= (hist.sum() + 1e-8)
        return hist

    hists = [lbp_histogram(f) for f in frames]
    diffs = [np.abs(hists[i] - hists[i+1]).sum() for i in range(len(hists)-1)]
    if not diffs:
        return 0.5
    return float(min(1.0, np.mean(diffs) / TEMPORAL_CONFIG["texture_threshold"]))


def _score_edge_consistency(frames: list[np.ndarray]) -> float:
    """
    지표 5: 엣지 일관성
    AI 영상은 물체 경계선이 프레임마다 흔들리는 경향이 있습니다.
    Canny 엣지 맵의 프레임 간 차이 편차가 클수록 AI 의심.
    """
    def edge_map(frame: np.ndarray) -> np.ndarray:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
        return edges.astype(float) / 255.0

    edges = [edge_map(f) for f in frames]
    diffs = [np.abs(edges[i] - edges[i+1]).mean() for i in range(len(edges)-1)]
    if not diffs:
        return 0.5
    return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["edge_threshold"]))


def _analyze_temporal(segments: list[list[np.ndarray]], **kwargs) -> AnalyzerResult:
    """
    시공간 분석기 메인 함수.

    [원리]
      연속 프레임들 사이의 광류를 계산하고 5가지 불일치 지표를 측정합니다.
      AI 영상은 시간 축에서 자연스럽지 못한 패턴이 남기 때문에
      이 5가지 지표의 가중 평균이 높으면 AI 의심입니다.

    [구간 평균을 쓰는 이유]
      영상의 특정 구간만 AI처럼 보일 수 있습니다.
      여러 구간의 평균을 내면 더 안정적인 판단이 가능합니다.

    Args:
        segments: extract_temporal_frames()의 반환값
                  [[구간1 프레임들], [구간2 프레임들], ...]
    """
    if not segments:
        return AnalyzerResult(
            score=0.5, status="skip",
            reason="시공간: 분석할 프레임 없음",
        )

    w          = TEMPORAL_CONFIG["flow_weights"]
    seg_scores = []

    for seg_frames in segments:
        if len(seg_frames) < 2:
            continue

        flows = [
            _compute_optical_flow(seg_frames[i], seg_frames[i+1])
            for i in range(len(seg_frames) - 1)
        ]

        s_mag  = _score_magnitude_inconsistency(flows)
        s_dir  = _score_direction_inconsistency(flows)
        s_diff = _score_frame_difference(seg_frames)
        s_tex  = _score_texture_consistency(seg_frames)
        s_edge = _score_edge_consistency(seg_frames)

        seg_score = (
            s_mag  * w["magnitude_inconsistency"] +
            s_dir  * w["direction_inconsistency"] +
            s_diff * w["frame_difference"]        +
            s_tex  * w["texture_consistency"]     +
            s_edge * w["edge_consistency"]
        )
        seg_scores.append({
            "score": seg_score,
            "mag": s_mag, "dir": s_dir,
            "diff": s_diff, "tex": s_tex, "edge": s_edge,
        })

    if not seg_scores:
        return AnalyzerResult(
            score=0.5, status="skip",
            reason="시공간: 유효한 구간 없음",
        )

    final_score = float(np.mean([s["score"] for s in seg_scores]))
    best        = max(seg_scores, key=lambda x: x["score"])

    return AnalyzerResult(
        score=final_score,
        status="ok",
        reason=(
            f"시공간: 이동불일치={best['mag']:.3f}, 방향불일치={best['dir']:.3f}, "
            f"프레임차분={best['diff']:.3f}, 텍스처={best['tex']:.3f}, 엣지={best['edge']:.3f} "
            f"(구간 {len(seg_scores)}개 평균)"
        ),
        detail={"segments": seg_scores},
    )


# ════════════════════════════════════════════════════════
#  분석기 Registry
# ════════════════════════════════════════════════════════

# 새 분석기를 추가할 때 여기에만 등록하면 됩니다.
# config.py의 ANALYZERS에 이름을 추가하는 것도 잊지 마세요.
ANALYZER_MAP = {
    "clip":      _analyze_clip,
    "frequency": _analyze_frequency,
    "metadata":  _analyze_metadata,
    "temporal":  _analyze_temporal,
    # "rppg":      _analyze_rppg,       # Phase B 추가 시
    # "physics":   _analyze_physics,    # Phase C 추가 시
    # "cnn_detect": _analyze_cnn,       # Phase A 추가 시
}


# ════════════════════════════════════════════════════════
#  앙상블
# ════════════════════════════════════════════════════════

def _ensemble(results: dict[str, AnalyzerResult]) -> float:
    """
    각 분석기의 결과를 가중 평균으로 합산합니다.

    status가 "error" 또는 "skip"인 모듈은 앙상블에서 제외됩니다.
    제외된 모듈의 가중치는 남은 모듈에 비례 배분됩니다.

    예: clip이 error면 clip 0.45가 나머지 3개에 비례해서 재분배됨.
    """
    weighted_sum = 0.0
    total_weight = 0.0

    for name, result in results.items():
        if result.status != "ok":
            continue  # error / skip 모듈 제외
        weight = ANALYZER_WEIGHTS.get(name, 0.0)
        weighted_sum += result.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.5  # 모든 모듈 실패 시 중립값 반환

    return float(np.clip(weighted_sum / total_weight, 0.0, 1.0))


# ════════════════════════════════════════════════════════
#  백엔드 호출 진입점 (함수명/인자명 변경 금지)
# ════════════════════════════════════════════════════════

def run_ai_video_analysis(video_path: str, output_dir: str) -> dict:
    """
    [백엔드 호출용 핵심 함수 — 이름/인자 변경 금지]

    전체 파이프라인을 순서대로 실행하고 결과를 반환합니다.

    실행 순서:
      0. 입력 검증 (형식/길이 확인)
      1. 프레임 추출 (균등 + 연속)
      2. 영상 타입 판별 (미래 분기용)
      3. 분석기 실행 (ANALYZERS 목록 기반)
      4. 앙상블 (가중 평균)
      5. 증거 프레임 저장
      6. 결과 JSON 조립 및 반환

    Args:
        video_path : 분석할 영상의 절대 경로
        output_dir : 증거 프레임을 저장할 폴더 경로

    Returns:
        성공: {
            "status":         "success",
            "is_ai":          bool,
            "confidence":     float,      # 0~1
            "risk_level":     str,        # HIGH / MEDIUM / LOW
            "reliability":    str,        # normal / low
            "module_scores":  dict,       # 각 모듈별 점수
            "analysis_details": dict,
            "evidence_frames":  list,
        }
        실패: {"status": "error", "message": str}
    """
    try:
        # ── 0. 입력 검증 ──────────────────────────────────────────────────
        status, msg = _validate_video(video_path)
        if status == "REJECT":
            return {"status": "error", "message": msg}

        # ── 1. 프레임 추출 ────────────────────────────────────────────────
        frames, timestamps = extract_frames(video_path)
        if not frames:
            return {"status": "error", "message": "프레임 추출 실패"}

        temporal_segments = extract_temporal_frames(video_path)

        # ── 2. 영상 타입 판별 (미래 분기용) ──────────────────────────────
        video_type = _detect_video_type(video_path, frames)

        # ── 3. 분석기 실행 ────────────────────────────────────────────────
        # config.ANALYZERS에 등록된 분석기만 실행됩니다.
        # 각 분석기에는 모든 데이터를 kwargs로 넘겨서
        # 필요한 것만 꺼내 씁니다.
        analyzer_kwargs = {
            "frames":            frames,
            "timestamps":        timestamps,
            "temporal_segments": temporal_segments,
            "video_path":        video_path,
            "video_type":        video_type,
        }

        # 분석기별 인자 매핑 (각 함수가 필요한 인자를 명시적으로 전달)
        analyzer_arg_map = {
            "clip":      {"frames": frames},
            "frequency": {"frames": frames},
            "metadata":  {"video_path": video_path},
            "temporal":  {"segments": temporal_segments},
        }

        results: dict[str, AnalyzerResult] = {}
        for name in ANALYZERS:
            fn = ANALYZER_MAP.get(name)
            if fn is None:
                continue
            try:
                args = analyzer_arg_map.get(name, {})
                results[name] = fn(**args)
            except Exception as e:
                results[name] = AnalyzerResult(
                    score=0.5, status="error",
                    reason=f"{name} 오류: {e}",
                )

        # ── 4. 앙상블 ─────────────────────────────────────────────────────
        final_score = _ensemble(results)

        # ── 5. 증거 프레임 저장 ───────────────────────────────────────────
        # CLIP similarity 기반으로 AI 의심도 높은 프레임 순서로 정렬
        # probability = 1.0 - similarity (낮은 유사도 = 높은 AI 의심)
        sorted_ts    = timestamps
        probabilities = None

        clip_result = results.get("clip")
        if clip_result and clip_result.status == "ok":
            similarities = clip_result.detail.get("similarities", [])
            if similarities and len(similarities) == len(timestamps) - 1:
                ts_prob_pairs = [
                    (ts, 1.0 - sim)
                    for ts, sim in zip(timestamps[:-1], similarities)
                ]
                # AI 의심도 높은 순서로 정렬
                ts_prob_pairs = sorted(
                    ts_prob_pairs,
                    key=lambda x: x[1],
                    reverse=True,
                )
                sorted_ts     = [ts for ts, _ in ts_prob_pairs]
                probabilities = [prob for _, prob in ts_prob_pairs]

        evidence_frames = save_evidence_frames(
            video_path=video_path,
            output_dir=output_dir,
            timestamps=sorted_ts,
            probabilities=probabilities,
            top_n=3,
        )

        # ── 6. 결과 조립 및 반환 ─────────────────────────────────────────
        result_json = build_result_json(
            final_score=final_score,
            results=results,
            weights=ANALYZER_WEIGHTS,
            evidence_frames=evidence_frames,
        )

        # duration 추가 (영상 길이, 초 단위)
        result_json["duration"] = _get_video_duration(video_path)

        return result_json

    except Exception:
        return {
            "status":  "error",
            "message": f"분석 중 예외 발생:\n{traceback.format_exc()}",
        }


def _get_video_duration(video_path: str) -> float:
    """영상 길이를 초 단위로 반환합니다."""
    cap = cv2.VideoCapture(video_path)
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if fps <= 0:
        return 0.0
    return round(total_frames / fps, 2)
