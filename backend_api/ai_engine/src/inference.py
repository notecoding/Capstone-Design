"""
ai_engine/src/inference.py

백엔드가 호출하는 진입점입니다.
함수명/인자명은 백엔드와의 약속이므로 변경 금지:
  run_ai_video_analysis(video_path: str, output_dir: str)

v2 변경사항:
  - _analyze_temporal() 추가 (시공간 분석기)
  - extract_temporal_frames() 연동
  - config.py temporal 가중치 활성화
"""

import os
import subprocess
import json
import traceback
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ai_engine.src.config import (
    ANALYZER_WEIGHTS, AI_THRESHOLD, RISK_THRESHOLDS,
    CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG,
    VIDEO_CONFIG, TEMPORAL_CONFIG,
)
from ai_engine.src.preprocess import (
    extract_frames,
    extract_temporal_frames,
    save_evidence_frames,
)


# ════════════════════════════════════════════════════════
#  CLIP 모델 싱글턴
# ════════════════════════════════════════════════════════

_clip_model      = None
_clip_preprocess = None
_clip_tokenizer  = None
_ai_text_feats   = None
_real_text_feats = None


def _load_clip():
    global _clip_model, _clip_preprocess, _clip_tokenizer
    global _ai_text_feats, _real_text_feats

    if _clip_model is not None:
        return

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

    def encode_texts(texts):
        tokens = _clip_tokenizer(texts).to(device)
        with torch.no_grad():
            feats = _clip_model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats

    _ai_text_feats   = encode_texts(CLIP_CONFIG["ai_prompts"])
    _real_text_feats = encode_texts(CLIP_CONFIG["real_prompts"])


# ════════════════════════════════════════════════════════
#  분석기 1: CLIP
# ════════════════════════════════════════════════════════

def _analyze_clip(frames: list[np.ndarray]) -> tuple[float, str, list[float]]:
    import torch

    _load_clip()
    device = CLIP_CONFIG["device"]
    frame_scores = []

    for frame in frames:
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

    avg    = float(np.mean(frame_scores))
    std    = float(np.std(frame_scores))
    reason = f"CLIP: 평균 {avg:.2%}, 표준편차 {std:.3f} (프레임 {len(frames)}개)"
    return avg, reason, frame_scores


# ════════════════════════════════════════════════════════
#  분석기 2: FFT 주파수 분석
# ════════════════════════════════════════════════════════

def _analyze_frequency(frames: list[np.ndarray]) -> tuple[float, str]:
    threshold = FREQUENCY_CONFIG["high_freq_threshold"]
    all_hf, all_rv, all_da = [], [], []

    for frame in frames:
        gray      = np.mean(frame, axis=2)
        fft_shift = np.fft.fftshift(np.fft.fft2(gray))
        mag       = np.log1p(np.abs(fft_shift))
        h, w      = mag.shape
        cx, cy    = w // 2, h // 2

        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        r    = min(h, w) // 4
        lo   = mag[dist <= r].sum()
        hi   = mag[dist >  r].sum()
        all_hf.append(hi / (lo + hi + 1e-8))

        profile = []
        for rr in range(1, min(cx, cy)):
            mask = (dist >= rr - 0.5) & (dist < rr + 0.5)
            if mask.sum() > 0:
                profile.append(mag[mask].mean())
        arr = np.array(profile)
        all_rv.append(float(np.var(arr) / (np.mean(arr) + 1e-8)))

        he = mag[cy - 2:cy + 2, :].sum()
        ve = mag[:, cx - 2:cx + 2].sum()
        all_da.append(abs(he - ve) / (he + ve + 1e-8))

    avg_hf = float(np.mean(all_hf))
    avg_rv = float(np.mean(all_rv))
    avg_da = float(np.mean(all_da))

    hf_score = max(0.0, min(1.0, 1.0 - abs(avg_hf - threshold) / threshold))
    rv_score = min(1.0, avg_rv / 5.0)
    da_score = min(1.0, avg_da * 3.0)
    score    = hf_score * 0.4 + rv_score * 0.4 + da_score * 0.2

    reason = (
        f"FFT: 고주파비={avg_hf:.3f}, "
        f"방사분산={avg_rv:.3f}, "
        f"방향비대칭={avg_da:.3f}"
    )
    return float(score), reason


# ════════════════════════════════════════════════════════
#  분석기 3: 메타데이터
# ════════════════════════════════════════════════════════

def _analyze_metadata(video_path: str) -> tuple[float, str, list[dict]]:
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
    except Exception:
        return 0.5, "ffprobe 실패", []

    if not data:
        return 0.5, "메타데이터 없음", []

    fmt     = data.get("format", {})
    streams = data.get("streams", [])
    tags    = fmt.get("tags", {})

    components = []
    reasons    = []

    # 1. 인코더 이름
    encoder_str = " ".join([
        tags.get("encoder",     ""),
        tags.get("comment",     ""),
        tags.get("description", ""),
        fmt.get("format_long_name", ""),
    ]).lower()

    found = [kw for kw in METADATA_CONFIG["suspicious_encoders"] if kw in encoder_str]
    if found:
        components.append(0.95)
        reasons.append(f"의심 인코더: {found}")
    else:
        components.append(0.20)

    # 2. C2PA
    if any("c2pa" in str(v).lower() for v in tags.values()):
        components.append(0.90)
        reasons.append("C2PA AI 생성 마커 감지")
    else:
        components.append(0.25)

    # 3. AI 전형 해상도
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
    return score, reason, []


# ════════════════════════════════════════════════════════
#  분석기 4: 시공간 분석 (v2 신규)
# ════════════════════════════════════════════════════════

def _compute_optical_flow(f1: np.ndarray, f2: np.ndarray) -> np.ndarray:
    """두 프레임 사이의 광류(Optical Flow)를 계산합니다."""
    g1   = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2   = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(
        g1, g2, None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )
    return flow  # shape: (H, W, 2) — (x방향, y방향)


def _score_magnitude_inconsistency(flows: list[np.ndarray]) -> float:
    """
    지표 1: 광류 이동량 불일치
    AI 영상은 프레임 간 이동량이 갑자기 튀는 경우가 많음.
    이동량의 표준편차가 클수록 AI 의심.
    """
    mags = []
    for flow in flows:
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        mags.append(mag.mean())

    if len(mags) < 2:
        return 0.5

    std   = float(np.std(mags))
    threshold = TEMPORAL_CONFIG["magnitude_threshold"]
    score = min(1.0, std / threshold)
    return score


def _score_direction_inconsistency(flows: list[np.ndarray]) -> float:
    """
    지표 2: 광류 방향 불일치
    AI 영상은 움직임 방향이 프레임마다 갑자기 바뀌는 경우가 있음.
    연속 프레임 간 방향 변화량의 평균이 클수록 AI 의심.
    """
    angles = []
    for flow in flows:
        angle = np.arctan2(flow[..., 1], flow[..., 0])
        angles.append(angle.mean())

    if len(angles) < 2:
        return 0.5

    diffs = [abs(angles[i+1] - angles[i]) for i in range(len(angles) - 1)]
    avg_diff  = float(np.mean(diffs))
    threshold = TEMPORAL_CONFIG["direction_threshold"]
    score     = min(1.0, avg_diff / (threshold * np.pi))
    return score


def _score_frame_difference(frames: list[np.ndarray]) -> float:
    """
    지표 3: 프레임 차분
    AI 영상은 배경이 미묘하게 변하는 패턴이 있음.
    인접 프레임의 픽셀 차이 평균이 불규칙할수록 AI 의심.
    """
    diffs = []
    for i in range(len(frames) - 1):
        diff = np.abs(
            frames[i].astype(float) - frames[i+1].astype(float)
        ).mean()
        diffs.append(diff)

    if not diffs:
        return 0.5

    std       = float(np.std(diffs))
    threshold = TEMPORAL_CONFIG["diff_threshold"]
    score     = min(1.0, std / threshold)
    return score


def _score_texture_consistency(frames: list[np.ndarray]) -> float:
    """
    지표 4: 텍스처 일관성 (LBP 기반)
    AI 영상은 머리카락, 손가락 같은 세밀한 텍스처가
    프레임마다 달라지는 경향이 있음.
    LBP 히스토그램의 프레임 간 차이가 클수록 AI 의심.
    """
    def lbp_histogram(frame: np.ndarray) -> np.ndarray:
        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        radius = 1
        n_points = 8

        lbp = np.zeros_like(gray, dtype=np.uint8)
        for i in range(n_points):
            angle = 2 * np.pi * i / n_points
            dx    = int(round(radius * np.cos(angle)))
            dy    = int(round(radius * np.sin(angle)))

            shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
            lbp    += (shifted >= gray).astype(np.uint8) * (2 ** i)

        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist    = hist.astype(float)
        hist   /= (hist.sum() + 1e-8)
        return hist

    hists = [lbp_histogram(f) for f in frames]
    diffs = []
    for i in range(len(hists) - 1):
        diff = np.abs(hists[i] - hists[i+1]).sum()
        diffs.append(diff)

    if not diffs:
        return 0.5

    avg_diff  = float(np.mean(diffs))
    threshold = TEMPORAL_CONFIG["texture_threshold"]
    score     = min(1.0, avg_diff / threshold)
    return score


def _score_edge_consistency(frames: list[np.ndarray]) -> float:
    """
    지표 5: 엣지 일관성
    AI 영상은 물체 경계선이 프레임마다 흔들리는 경향이 있음.
    엣지 맵의 프레임 간 차이가 클수록 AI 의심.
    """
    def edge_map(frame: np.ndarray) -> np.ndarray:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
        return edges.astype(float) / 255.0

    edges = [edge_map(f) for f in frames]
    diffs = []
    for i in range(len(edges) - 1):
        diff = np.abs(edges[i] - edges[i+1]).mean()
        diffs.append(diff)

    if not diffs:
        return 0.5

    std       = float(np.std(diffs))
    threshold = TEMPORAL_CONFIG["edge_threshold"]
    score     = min(1.0, std / threshold)
    return score


def _analyze_temporal(segments: list[list[np.ndarray]]) -> tuple[float, str]:
    """
    시공간 분석기 메인 함수.
    구간별 프레임들을 받아서 5가지 지표를 계산하고 가중 평균을 냄.

    Args:
        segments: extract_temporal_frames()의 반환값
                  [[구간1 프레임들], [구간2 프레임들], ...]

    Returns:
        score : 0~1 (높을수록 AI 의심)
        reason: 판단 근거 문자열
    """
    if not segments:
        return 0.5, "시공간: 분석할 프레임 없음"

    w = TEMPORAL_CONFIG["flow_weights"]
    seg_scores = []

    for seg_frames in segments:
        if len(seg_frames) < 2:
            continue

        # 광류 계산 (인접 프레임 쌍마다)
        flows = [
            _compute_optical_flow(seg_frames[i], seg_frames[i+1])
            for i in range(len(seg_frames) - 1)
        ]

        # 5가지 지표 계산
        s_mag  = _score_magnitude_inconsistency(flows)
        s_dir  = _score_direction_inconsistency(flows)
        s_diff = _score_frame_difference(seg_frames)
        s_tex  = _score_texture_consistency(seg_frames)
        s_edge = _score_edge_consistency(seg_frames)

        # 가중 평균
        seg_score = (
            s_mag  * w["magnitude_inconsistency"] +
            s_dir  * w["direction_inconsistency"] +
            s_diff * w["frame_difference"]        +
            s_tex  * w["texture_consistency"]     +
            s_edge * w["edge_consistency"]
        )
        seg_scores.append({
            "score": seg_score,
            "mag":   s_mag,
            "dir":   s_dir,
            "diff":  s_diff,
            "tex":   s_tex,
            "edge":  s_edge,
        })

    if not seg_scores:
        return 0.5, "시공간: 유효한 구간 없음"

    final_score = float(np.mean([s["score"] for s in seg_scores]))

    # 대표 구간(점수 높은 구간) 기준으로 reason 생성
    best = max(seg_scores, key=lambda x: x["score"])
    reason = (
        f"시공간: 이동불일치={best['mag']:.3f}, "
        f"방향불일치={best['dir']:.3f}, "
        f"프레임차분={best['diff']:.3f}, "
        f"텍스처={best['tex']:.3f}, "
        f"엣지={best['edge']:.3f} "
        f"(구간 {len(seg_scores)}개 평균)"
    )
    return final_score, reason


# ════════════════════════════════════════════════════════
#  앙상블
# ════════════════════════════════════════════════════════

def _ensemble(scores: dict[str, float]) -> float:
    weighted_sum = 0.0
    total_weight = 0.0
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
    level = _risk_level(score)
    base  = {
        "HIGH":   "AI 생성 영상으로 판별되었습니다.",
        "MEDIUM": "AI 생성 가능성이 있으나 확실하지 않습니다.",
        "LOW":    "실제 촬영 영상으로 판별되었습니다.",
    }[level]

    details = [
        r for r in reasons.values()
        if r and "없음" not in r and "실패" not in r and "오류" not in r
    ]
    return base + (" 근거: " + " / ".join(details) if details else "")


# ════════════════════════════════════════════════════════
#  백엔드 호출 진입점 (함수명/인자명 변경 금지)
# ════════════════════════════════════════════════════════

def run_ai_video_analysis(video_path: str, output_dir: str) -> dict:
    """
    [백엔드 호출용 핵심 함수 - 이름/인자 변경 금지]

    Args:
        video_path : 분석할 영상의 절대 경로
        output_dir : 결과 이미지를 저장할 폴더 경로

    Returns:
        성공: {"status": "success", "is_ai": bool, "confidence": float,
               "analysis_details": {...}, "evidence_frames": [...]}
        실패: {"status": "error", "message": str}
    """
    try:
        # ── 0. 입력 검증 ──────────────────────────────────────────────────
        if not os.path.exists(video_path):
            return {"status": "error", "message": f"파일 없음: {video_path}"}

        ext = Path(video_path).suffix.lower()
        if ext not in VIDEO_CONFIG["supported_formats"]:
            return {
                "status":  "error",
                "message": f"지원하지 않는 형식: {ext}",
            }

        # ── 1. 프레임 추출 ────────────────────────────────────────────────
        frames, timestamps = extract_frames(video_path)
        if not frames:
            return {"status": "error", "message": "프레임 추출 실패"}

        # 시공간 분석용 연속 프레임 (v2)
        temporal_segments = extract_temporal_frames(video_path)

        # ── 2. 분석기 실행 ────────────────────────────────────────────────
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

        # 시공간 분석 (v2)
        try:
            temp_score, temp_reason = _analyze_temporal(temporal_segments)
            scores["temporal"]  = temp_score
            reasons["temporal"] = temp_reason
        except Exception as e:
            scores["temporal"]  = None
            reasons["temporal"] = f"시공간 오류: {e}"

        # ── 3. 앙상블 ─────────────────────────────────────────────────────
        final_score = _ensemble(scores)
        is_ai       = final_score >= AI_THRESHOLD

        # ── 4. evidence 프레임 저장 ───────────────────────────────────────
        if frame_scores_clip and len(frame_scores_clip) == len(timestamps):
            sorted_ts = [
                ts for _, ts in sorted(
                    zip(frame_scores_clip, timestamps), reverse=True
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

        # ── 5. 반환 ───────────────────────────────────────────────────────
        return {
            "status":     "success",
            "is_ai":      bool(is_ai),
            "confidence": round(final_score, 4),
            "analysis_details": {
                "details":          _build_description(final_score, reasons),
                "detected_regions": detected_regions,
            },
            "evidence_frames": evidence_frames,
        }

    except Exception:
        return {
            "status":  "error",
            "message": f"분석 중 예외 발생: {traceback.format_exc()}",
        }