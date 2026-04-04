"""
ai_engine/src/inference.py

백엔드가 호출하는 진입점입니다.
함수명/인자명은 백엔드와의 약속이므로 변경 금지:
  run_ai_video_analysis(video_path: str, output_dir: str)

내부 구조:
  1. VideoPreprocessor  : 영상 → 프레임 추출
  2. CLIPAnalyzer       : Zero-shot AI 판별 (가중치 55%)
  3. FrequencyAnalyzer  : FFT 주파수 분석   (가중치 30%)
  4. MetadataAnalyzer   : 메타데이터 분석   (가중치 15%)
  5. _ensemble          : 가중 평균 → 최종 점수
  6. save_evidence_frames: 결과 프레임 output_dir 저장
"""

import os
import subprocess
import json
import traceback
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.config import (
    ANALYZER_WEIGHTS, AI_THRESHOLD, RISK_THRESHOLDS,
    CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG, VIDEO_CONFIG,
)
from src.preprocess import extract_frames, save_evidence_frames


# ════════════════════════════════════════════════════════
#  모델 싱글턴 (최초 1회만 로드)
# ════════════════════════════════════════════════════════

_clip_model      = None
_clip_preprocess = None
_clip_tokenizer  = None
_ai_text_feats   = None
_real_text_feats = None


def _load_clip():
    """CLIP 모델을 최초 1회만 로드합니다. (이후엔 캐시 사용)"""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    global _ai_text_feats, _real_text_feats

    if _clip_model is not None:
        return  # 이미 로드됨

    import open_clip
    import torch

    device = CLIP_CONFIG["device"]
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        CLIP_CONFIG["model_name"],
        pretrained=CLIP_CONFIG["pretrained"],
        device=device,
    )
    _clip_tokenizer = open_clip.get_tokenizer(CLIP_CONFIG["model_name"])
    _clip_model.eval()

    # 텍스트 임베딩 미리 계산
    def encode_texts(texts):
        tokens = _clip_tokenizer(texts).to(device)
        with torch.no_grad():
            feats = _clip_model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats

    _ai_text_feats   = encode_texts(CLIP_CONFIG["ai_prompts"])
    _real_text_feats = encode_texts(CLIP_CONFIG["real_prompts"])


# ════════════════════════════════════════════════════════
#  개별 분석기
# ════════════════════════════════════════════════════════

def _analyze_clip(frames: list[np.ndarray]) -> tuple[float, str, list[float]]:
    """
    CLIP Zero-shot으로 각 프레임이 AI 생성 영상인지 판별.

    Returns:
        score       : 평균 AI 확률 (0~1)
        reason      : 판단 근거 문자열
        frame_scores: 프레임별 점수 리스트 (evidence 선택에 사용)
    """
    import torch

    _load_clip()
    device = CLIP_CONFIG["device"]

    frame_scores = []
    for frame in frames:
        # BGR → RGB → PIL
        rgb     = frame[:, :, ::-1]
        pil_img = Image.fromarray(rgb.astype(np.uint8))
        tensor  = _clip_preprocess(pil_img).unsqueeze(0).to(device)

        with torch.no_grad():
            img_feat = _clip_model.encode_image(tensor)
            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)

        ai_sim   = (img_feat @ _ai_text_feats.T).mean().item()
        real_sim = (img_feat @ _real_text_feats.T).mean().item()

        logits = torch.tensor([ai_sim, real_sim]) * 100.0
        probs  = torch.softmax(logits, dim=0)
        frame_scores.append(float(probs[0]))

    avg   = float(np.mean(frame_scores))
    std   = float(np.std(frame_scores))
    reason = f"CLIP: 평균 {avg:.2%}, 표준편차 {std:.3f} (프레임 {len(frames)}개)"

    return avg, reason, frame_scores


def _analyze_frequency(frames: list[np.ndarray]) -> tuple[float, str]:
    """
    FFT 주파수 도메인 분석.
    AI 영상은 업샘플링 아티팩트로 주파수 패턴이 비정상적.

    Returns:
        score : AI 확률 (0~1)
        reason: 판단 근거
    """
    threshold = FREQUENCY_CONFIG["high_freq_threshold"]
    all_hf, all_rv, all_da = [], [], []

    for frame in frames:
        gray      = np.mean(frame, axis=2)
        fft_shift = np.fft.fftshift(np.fft.fft2(gray))
        mag       = np.log1p(np.abs(fft_shift))
        h, w      = mag.shape
        cx, cy    = w // 2, h // 2

        # 고주파 에너지 비율
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        r    = min(h, w) // 4
        lo   = mag[dist <= r].sum()
        hi   = mag[dist >  r].sum()
        all_hf.append(hi / (lo + hi + 1e-8))

        # 방사형 분산 (아티팩트 지표)
        profile = []
        for rr in range(1, min(cx, cy)):
            mask = (dist >= rr - 0.5) & (dist < rr + 0.5)
            if mask.sum() > 0:
                profile.append(mag[mask].mean())
        arr = np.array(profile)
        all_rv.append(float(np.var(arr) / (np.mean(arr) + 1e-8)))

        # 방향성 비대칭
        he = mag[cy - 2:cy + 2, :].sum()
        ve = mag[:, cx - 2:cx + 2].sum()
        all_da.append(abs(he - ve) / (he + ve + 1e-8))

    avg_hf = float(np.mean(all_hf))
    avg_rv = float(np.mean(all_rv))
    avg_da = float(np.mean(all_da))

    hf_score  = max(0.0, min(1.0, 1.0 - abs(avg_hf - threshold) / threshold))
    rv_score  = min(1.0, avg_rv / 5.0)
    da_score  = min(1.0, avg_da * 3.0)
    score     = hf_score * 0.4 + rv_score * 0.4 + da_score * 0.2

    reason = (
        f"FFT: 고주파비={avg_hf:.3f}, "
        f"방사분산={avg_rv:.3f}, "
        f"방향비대칭={avg_da:.3f}"
    )
    return float(score), reason


def _analyze_metadata(video_path: str) -> tuple[float, str, list[dict]]:
    """
    ffprobe로 인코더명, 비트레이트, 해상도 등 메타데이터 분석.
    AI 도구(runway, pika 등)의 흔적을 탐색.

    Returns:
        score           : AI 확률 (0~1)
        reason          : 판단 근거
        detected_regions: 픽셀 아티팩트 좌표 (현재는 빈 리스트, v2에서 구현)
    """
    # ffprobe 실행
    try:
        result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",      # 이 줄 추가
            errors="ignore",        # 이 줄 추가
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except Exception:
        return 0.5, "ffprobe 실패 (설치 필요)", []

    if not data:
        return 0.5, "메타데이터 없음", []

    fmt     = data.get("format", {})
    streams = data.get("streams", [])
    tags    = fmt.get("tags", {})

    components = []
    reasons    = []

    # 1. 인코더 이름 확인
    encoder_str = " ".join([
        tags.get("encoder",     ""),
        tags.get("comment",     ""),
        tags.get("description", ""),
        fmt.get("format_long_name", ""),
    ]).lower()

    found = [kw for kw in METADATA_CONFIG["suspicious_encoders"] if kw in encoder_str]
    if found:
        components.append(0.95)
        reasons.append(f"의심 인코더 발견: {found}")
    else:
        components.append(0.20)

    # 2. C2PA AI 마커 확인
    if any("c2pa" in str(v).lower() for v in tags.values()):
        components.append(0.90)
        reasons.append("C2PA AI 생성 마커 감지")
    else:
        components.append(0.25)

    # 3. AI 전형 해상도 (512x512, 768x512 등)
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if video_streams:
        w, h = video_streams[0].get("width", 0), video_streams[0].get("height", 0)
        unusual_ai_res = {(512, 512), (768, 512), (512, 768), (1024, 576), (576, 1024)}
        if (w, h) in unusual_ai_res:
            components.append(0.75)
            reasons.append(f"AI 전형 해상도: {w}x{h}")
        else:
            components.append(0.20)

    score  = float(np.mean(components)) if components else 0.5
    reason = " | ".join(reasons) if reasons else "메타데이터 이상 없음"

    # detected_regions: v2에서 실제 픽셀 아티팩트 좌표 반환 예정
    detected_regions: list[dict] = []

    return score, reason, detected_regions


# ════════════════════════════════════════════════════════
#  앙상블
# ════════════════════════════════════════════════════════

def _ensemble(scores: dict[str, float]) -> float:
    """가중 평균으로 최종 AI 확률 계산."""
    weighted_sum  = 0.0
    total_weight  = 0.0
    for name, weight in ANALYZER_WEIGHTS.items():
        s = scores.get(name)
        if s is not None and weight > 0:
            weighted_sum += s * weight
            total_weight += weight
    if total_weight == 0:
        return 0.5
    return float(np.clip(weighted_sum / total_weight, 0.0, 1.0))


def _risk_level(score: float) -> str:
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _build_description(score: float, reasons: dict[str, str]) -> str:
    """프론트엔드에 보여줄 한국어 설명 생성."""
    level = _risk_level(score)
    base = {
        "HIGH":   "AI 생성 영상으로 판별되었습니다.",
        "MEDIUM": "AI 생성 가능성이 있으나 확실하지 않습니다.",
        "LOW":    "실제 촬영 영상으로 판별되었습니다.",
    }[level]

    details = []
    for name, reason in reasons.items():
        if reason and "없음" not in reason and "실패" not in reason:
            details.append(reason)

    return base + (" 근거: " + " / ".join(details) if details else "")


# ════════════════════════════════════════════════════════
#  백엔드 호출 진입점 (함수명/인자명 변경 금지)
# ════════════════════════════════════════════════════════

def run_ai_video_analysis(video_path: str, output_dir: str) -> dict:
    """
    [백엔드 호출용 핵심 함수 - 이름/인자 변경 금지]

    Args:
        video_path : 분석할 영상의 절대 경로 (백엔드가 전달)
        output_dir : 결과 이미지를 저장할 폴더 경로 (백엔드가 지정)

    Returns:
        성공 시:
        {
            "status": "success",
            "is_ai": bool,
            "confidence": float,          # 0.0 ~ 1.0
            "analysis_details": {
                "details": str,           # 한국어 설명
                "detected_regions": list  # 픽셀 아티팩트 좌표 (v2)
            },
            "evidence_frames": [
                {"timestamp": float, "file_name": str}
            ]
        }

        실패 시:
        {
            "status": "error",
            "message": str
        }
    """
    try:
        # ── 0. 입력 파일 검증 ──────────────────────────────────────
        if not os.path.exists(video_path):
            return {"status": "error", "message": f"파일 없음: {video_path}"}

        ext = Path(video_path).suffix.lower()
        if ext not in VIDEO_CONFIG["supported_formats"]:
            return {
                "status":  "error",
                "message": f"지원하지 않는 형식: {ext}. 지원: {VIDEO_CONFIG['supported_formats']}",
            }

        # ── 1. 프레임 추출 ────────────────────────────────────────
        frames, timestamps = extract_frames(video_path)
        if not frames:
            return {"status": "error", "message": "프레임 추출 실패"}

        # ── 2. 분석기 실행 ────────────────────────────────────────
        scores  = {}
        reasons = {}
        frame_scores_clip = []

        # CLIP
        try:
            clip_score, clip_reason, frame_scores_clip = _analyze_clip(frames)
            scores["clip"]  = clip_score
            reasons["clip"] = clip_reason
        except Exception as e:
            scores["clip"]  = None
            reasons["clip"] = f"CLIP 오류: {e}"

        # FFT
        try:
            fft_score, fft_reason = _analyze_frequency(frames)
            scores["frequency"]  = fft_score
            reasons["frequency"] = fft_reason
        except Exception as e:
            scores["frequency"]  = None
            reasons["frequency"] = f"FFT 오류: {e}"

        # 메타데이터
        try:
            meta_score, meta_reason, detected_regions = _analyze_metadata(video_path)
            scores["metadata"]  = meta_score
            reasons["metadata"] = meta_reason
        except Exception as e:
            scores["metadata"]  = None
            reasons["metadata"] = f"메타데이터 오류: {e}"
            detected_regions    = []

        # ── 3. 앙상블 ─────────────────────────────────────────────
        final_score = _ensemble(scores)
        is_ai       = final_score >= AI_THRESHOLD

        # ── 4. evidence 프레임 저장 ───────────────────────────────
        # CLIP 점수가 높은 프레임 우선 저장
        if frame_scores_clip and len(frame_scores_clip) == len(timestamps):
            # 점수 높은 순으로 타임스탬프 정렬
            sorted_ts = [
                ts for _, ts in sorted(
                    zip(frame_scores_clip, timestamps),
                    reverse=True,
                )
            ]
        else:
            sorted_ts = timestamps

        evidence_frames = save_evidence_frames(
            video_path=video_path,
            output_dir=output_dir,
            timestamps=sorted_ts,
            top_n=3,
        )

        # ── 5. 결과 반환 ──────────────────────────────────────────
        return {
            "status":     "success",
            "is_ai":      bool(is_ai),
            "confidence": round(final_score, 4),
            "analysis_details": {
                "details":          _build_description(final_score, reasons),
                "detected_regions": detected_regions,  # v2에서 실제 좌표 반환
            },
            "evidence_frames": evidence_frames,
        }

    except Exception as e:
        return {
            "status":  "error",
            "message": f"분석 중 예외 발생: {traceback.format_exc()}",
        }
