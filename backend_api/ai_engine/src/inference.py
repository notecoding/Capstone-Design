"""
ai_engine/src/inference.py — 백엔드 호출 진입점

[백엔드와의 약속 — 변경 금지]
  run_ai_video_analysis(video_path, output_dir, targets=None, progress_callback=None)

[분석기 추가 방법]
  1. config.py ANALYZERS에 이름 추가
  2. config.py ANALYZER_WEIGHTS에 가중치 추가
  3. 이 파일에 _analyze_XXX() 작성 (AnalyzerResult 반환)
  4. ANALYZER_MAP에 등록
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
    CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG,
    VIDEO_CONFIG,
    # TEMPORAL_CONFIG,  # 시공간 분析기 비활성화
)
from ai_engine.src.preprocess import (
    extract_frames,
    # extract_temporal_frames,  # 시공간 분析기 비활성화
)
from ai_engine.src.postprocess import (
    save_evidence_frames,
    build_result_json,
)


# ── 진행 상황 콜백 ────────────────────────────────────────────

def _emit_progress(progress_callback, state, status, progress, message, selected_analyzers=None):
    """progress_callback이 있으면 진행 상황 전달, 없으면 무시"""
    if progress_callback is not None:
        progress_callback(state, status, progress, message, selected_analyzers)


# ── 영상 타입 판별 (미래 분기용 뼈대) ────────────────────────

def _detect_video_type(video_path: str, frames: list[np.ndarray]) -> dict:
    """
    [현재] 모든 플래그 False 고정.
    [미래] Phase B: has_face=True → rPPG 활성화
           Phase C: has_face=False → 물리 일관성 활성화
    반환값을 반드시 변수에 받아서 사용할 것.
    """
    return {
        "has_face":      False,
        "is_short":      False,
        "is_compressed": False,
    }


# ── 입력 검증 ─────────────────────────────────────────────────

def _validate_video(video_path: str) -> tuple[str, str, float]:
    """
    반환값: (status, message, duration)
    duration을 함께 반환해서 _get_video_duration 중복 계산 방지
    """
    if not os.path.exists(video_path):
        return "REJECT", f"파일 없음: {video_path}", 0.0

    ext = Path(video_path).suffix.lower()
    if ext not in VIDEO_CONFIG["supported_formats"]:
        return "REJECT", f"지원하지 않는 형식: {ext}", 0.0

    cap      = cv2.VideoCapture(video_path)
    fps      = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = round(n_frames / fps, 2) if fps > 0 else 0.0

    if duration < VIDEO_CONFIG["min_duration"]:
        return "REJECT", f"영상이 너무 짧음 ({duration:.1f}초)", 0.0
    if duration > VIDEO_CONFIG["max_duration"]:
        return "REJECT", f"영상이 너무 긺 ({duration:.0f}초)", 0.0

    return "OK", "", duration


# ── DeCoF 분류 헤드 ───────────────────────────────────────────
# colab_train.py의 CLIPClassifier와 완전히 동일한 구조 유지 필수
# 구조가 다르면 load_state_dict 키 불일치로 가중치 로드 실패

class _DeCoFClassifier(nn.Module):
    def __init__(self, feat_dim=768, n_frames=8):
        super().__init__()
        # 프레임 시간 순서를 Transformer가 인식하도록 위치 인코딩 추가
        self.pos_embed = nn.Parameter(
            torch.randn(1, n_frames, feat_dim) * 0.02
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=feat_dim, nhead=8,
            dim_feedforward=2048, dropout=0.05,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.mlp = nn.Sequential(
            nn.Linear(feat_dim, 256), nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(256, 1),
            # Sigmoid 없음 — BCEWithLogitsLoss로 학습
            # 추론 시 torch.sigmoid()로 수동 변환
        )

    def forward(self, x):
        x = x + self.pos_embed
        x = self.transformer(x)
        return self.mlp(x.mean(dim=1))


_classifier = None


def _load_classifier():
    """checkpoint_main.pth 로드 (싱글턴). 파일 없으면 fallback 모드로 동작"""
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


# ── CLIP 모델 싱글턴 ──────────────────────────────────────────

_clip_model      = None
_clip_preprocess = None


def _load_clip():
    """ViT-L-14 로드 (싱글턴). 요청마다 로드하면 수십 초 낭비"""
    global _clip_model, _clip_preprocess
    if _clip_model is not None:
        return

    import open_clip
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        CLIP_CONFIG["model_name"],
        pretrained=CLIP_CONFIG["pretrained"],
        device=CLIP_CONFIG["device"],
    )
    _clip_model.eval()


# ── 분석기 1: CLIP (DeCoF 방식) ──────────────────────────────

def _analyze_clip(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    """
    프레임 벡터 시퀀스를 Transformer에 입력해서 AI 확률 산출.
    가중치 없으면 프레임 간 유사도 기반 fallback으로 자동 동작.
    """
    _load_clip()
    device = CLIP_CONFIG["device"]

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
        return AnalyzerResult(score=0.5, status="skip", reason="CLIP: 프레임 수 부족")

    similarities = []
    for i in range(len(frame_feats) - 1):
        sim = (frame_feats[i] @ frame_feats[i+1].T).item()
        similarities.append(sim)
    avg_sim = float(np.mean(similarities))
    std_sim = float(np.std(similarities))

    _load_classifier()
    if _classifier is not None:
        feat_seq = torch.cat(frame_feats, dim=0).unsqueeze(0)  # (1, 8, 768)
        with torch.no_grad():
            logit = _classifier(feat_seq)
            score = float(torch.sigmoid(logit).item())  # logit → 확률
        reason = f"CLIP(DeCoF Transformer): AI 확률 {score:.3f}"
        used_classifier = True
    else:
        # AI 영상은 flickering으로 프레임 간 유사도가 낮음
        score  = float(np.clip(1.0 - avg_sim, 0.0, 1.0))
        reason = f"CLIP(fallback): 프레임 간 평균 유사도 {avg_sim:.3f} (낮을수록 AI 의심)"
        used_classifier = False

    return AnalyzerResult(
        score=score, status="ok", reason=reason,
        detail={
            "avg_similarity":    avg_sim,
            "std_similarity":    std_sim,
            "similarities":      similarities,
            "n_frames_analyzed": len(frame_feats),
            "used_classifier":   used_classifier,
        },
    )


# ── 분석기 2: FFT 주파수 분석 ────────────────────────────────

def _analyze_frequency(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    """
    FFT 주파수 분석기 — 기존 3가지 + 심화 3가지 지표로 AI 생성 흔적 탐지.

    기존 지표
      고주파 비율    전체 에너지 중 외곽(고주파) 영역 비율
      방사 분산      거리별 평균 에너지의 분산
      방향 비대칭    수평/수직 에너지 불균형

    심화 지표 (GAN/Diffusion 격자 패턴 탐지)
      격자 패턴 강도  주파수 스펙트럼의 규칙적 피크 간격
                     AI 모델이 업샘플링 과정에서 남기는 흔적
      주기적 artifact 자기상관으로 측정한 스펙트럼 주기성
      에너지 집중도   Gini 계수로 측정한 에너지 분포 불균등
    """
    try:
        from scipy import signal as scipy_signal
    except ImportError:
        return AnalyzerResult(
            score=0.5, status="error",
            reason="FFT심화: scipy 미설치 — pip install scipy"
        )

    threshold = FREQUENCY_CONFIG["high_freq_threshold"]

    # 기존 지표
    all_hf, all_rv, all_da = [], [], []

    # 심화 지표
    all_grid, all_periodic, all_conc = [], [], []

    for frame in frames:
        gray      = np.mean(frame, axis=2)
        fft_shift = np.fft.fftshift(np.fft.fft2(gray))
        mag       = np.log1p(np.abs(fft_shift))
        h, w      = mag.shape
        cx, cy    = w // 2, h // 2
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
        r    = min(h, w) // 4

        # ── 기존 지표 ─────────────────────────────────────────
        lo = mag[dist <= r].sum()
        hi = mag[dist >  r].sum()
        all_hf.append(hi / (lo + hi + 1e-8))

        profile = []
        for rr in range(1, min(cx, cy)):
            mask = (dist >= rr - 0.5) & (dist < rr + 0.5)
            if mask.sum() > 0:
                profile.append(mag[mask].mean())
        arr = np.array(profile)
        all_rv.append(float(np.var(arr) / (np.mean(arr) + 1e-8)))

        he = mag[cy-2:cy+2, :].sum()
        ve = mag[:, cx-2:cx+2].sum()
        all_da.append(abs(he - ve) / (he + ve + 1e-8))

        # ── 심화 지표 1: 격자 패턴 강도 ──────────────────────
        # 행/열 방향 합산 후 규칙적 피크 탐지
        row_profile = mag.mean(axis=1).copy()
        col_profile = mag.mean(axis=0).copy()
        # 중심 DC 성분 제거
        row_profile[int(h*0.45):int(h*0.55)] = 0
        col_profile[int(w*0.45):int(w*0.55)] = 0

        row_peaks, _ = scipy_signal.find_peaks(
            row_profile, height=row_profile.mean()*2, distance=5)
        col_peaks, _ = scipy_signal.find_peaks(
            col_profile, height=col_profile.mean()*2, distance=5)

        if len(row_peaks) >= 2 and len(col_peaks) >= 2:
            # np.clip으로 음수 방지 — 피크 간격이 불규칙할 때 음수 발생 가능
            row_reg = float(np.clip(
                1.0 - np.std(np.diff(row_peaks)) / (np.mean(np.diff(row_peaks)) + 1e-8),
                0.0, 1.0))
            col_reg = float(np.clip(
                1.0 - np.std(np.diff(col_peaks)) / (np.mean(np.diff(col_peaks)) + 1e-8),
                0.0, 1.0))
            peak_score = min(1.0, (len(row_peaks) + len(col_peaks)) / 20.0)
            grid = float(np.clip((row_reg + col_reg) / 2 * 0.7 + peak_score * 0.3, 0.0, 1.0))
        else:
            grid = 0.0
        all_grid.append(grid)

        # ── 심화 지표 2: 주기적 artifact ─────────────────────
        # 자기상관으로 스펙트럼 주기성 측정
        row_ac = mag.mean(axis=1) - mag.mean()
        autocorr = np.correlate(row_ac, row_ac, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        autocorr = autocorr / (autocorr[0] + 1e-8)
        ac_peaks, ac_props = scipy_signal.find_peaks(
            autocorr[1:], height=0.3, distance=3)
        periodic = float(ac_props['peak_heights'].max()) if len(ac_peaks) > 0 else 0.0
        all_periodic.append(float(np.clip(periodic, 0.0, 1.0)))

        # ── 심화 지표 3: 에너지 집중도 (Gini 계수) ───────────
        # 에너지가 특정 주파수에 집중될수록 AI 의심
        flat = np.sort(np.abs(mag.flatten()))  # 절댓값으로 음수 방지
        n = len(flat)
        if n == 0 or flat.sum() < 1e-8:
            all_conc.append(0.0)
            continue
        # Gini 계수 표준 공식: G = (2 * sum(i * x_i) / (n * sum(x_i))) - (n+1)/n
        indices = np.arange(1, n + 1)
        gini = float((2 * np.sum(indices * flat)) / (n * flat.sum()) - (n + 1) / n)
        all_conc.append(float(np.clip(gini, 0.0, 1.0)))

    # ── 최종 스코어 계산 ──────────────────────────────────────
    avg_hf  = float(np.mean(all_hf))
    avg_rv  = float(np.mean(all_rv))
    avg_da  = float(np.mean(all_da))
    avg_grid     = float(np.mean(all_grid))
    avg_periodic = float(np.mean(all_periodic))
    avg_conc     = float(np.mean(all_conc))

    # 기존 지표 스코어
    hf_score = max(0.0, min(1.0, 1.0 - abs(avg_hf - threshold) / threshold))
    rv_score = min(1.0, avg_rv / 5.0)
    da_score = min(1.0, avg_da * 3.0)
    base_score = hf_score * 0.4 + rv_score * 0.4 + da_score * 0.2

    # 심화 지표 스코어
    deep_score = avg_grid * 0.5 + avg_periodic * 0.3 + avg_conc * 0.2

    # 기존 40% + 심화 60% (심화가 더 신뢰도 높음)
    score = base_score * 0.4 + deep_score * 0.6

    return AnalyzerResult(
        score=float(np.clip(score, 0.0, 1.0)),
        status="ok",
        reason=(
            f"FFT: 고주파비={avg_hf:.3f}, 방사분산={avg_rv:.3f}, 방향비대칭={avg_da:.3f} | "
            f"격자패턴={avg_grid:.3f}, 주기성={avg_periodic:.3f}, 에너지집중={avg_conc:.3f}"
        ),
        detail={
            "high_freq_ratio":         avg_hf,
            "radial_variance":         avg_rv,
            "directional_asymm":       avg_da,
            "grid_pattern_score":      avg_grid,
            "periodic_artifact_score": avg_periodic,
            "spectral_concentration":  avg_conc,
        },
    )


# ── 분석기 3: 메타데이터 ─────────────────────────────────────

def _analyze_metadata(video_path: str, **kwargs) -> AnalyzerResult:
    """의심 인코더 키워드, C2PA 마커, AI 전형 해상도로 AI 생성 흔적 탐지"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="ignore",
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except Exception as e:
        return AnalyzerResult(score=0.5, status="error", reason=f"ffprobe 실패: {e}")

    if not data:
        return AnalyzerResult(score=0.5, status="skip", reason="메타데이터 없음")

    fmt     = data.get("format", {})
    streams = data.get("streams", [])
    tags    = fmt.get("tags", {})
    components, found_items = [], []

    encoder_str = " ".join([
        tags.get("encoder", ""), tags.get("comment", ""),
        tags.get("description", ""), fmt.get("format_long_name", ""),
    ]).lower()
    found_kw = [kw for kw in METADATA_CONFIG["suspicious_encoders"] if kw in encoder_str]
    if found_kw:
        components.append(0.95); found_items.append(f"의심 인코더: {found_kw}")
    else:
        components.append(0.20)

    if any("c2pa" in str(v).lower() for v in tags.values()):
        components.append(0.90); found_items.append("C2PA AI 생성 마커 감지")
    else:
        components.append(0.25)

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if video_streams:
        w = video_streams[0].get("width", 0)
        h = video_streams[0].get("height", 0)
        if (w, h) in METADATA_CONFIG["ai_resolutions"]:
            components.append(0.75); found_items.append(f"AI 전형 해상도: {w}x{h}")
        else:
            components.append(0.20)

    score  = float(np.mean(components)) if components else 0.5
    reason = " | ".join(found_items) if found_items else "메타데이터 이상 없음"
    return AnalyzerResult(score=score, status="ok", reason=reason,
                          detail={"found_items": found_items})


# ── 분석기 4: 시공간 분석 (현재 가중치 0 — 보류 중) ──────────
# 광류(Optical Flow) 기반 룰베이스 분석기.
# 최신 AI 영상(Sora, Gen2 등)은 시간적 일관성이 향상되어 효과 제한적.
# config.py에서 "temporal" 가중치를 0으로 설정해 앙상블에서 제외 중.
# [미래] Phase C에서 물리 일관성 기반 학습형 분석기로 교체 예정.

# def _compute_optical_flow(f1, f2):
#     g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
#     g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
#     return cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)

# def _score_magnitude_inconsistency(flows):
#     mags = [np.sqrt(f[...,0]**2 + f[...,1]**2).mean() for f in flows]
#     if len(mags) < 2: return 0.5
#     return float(min(1.0, np.std(mags) / TEMPORAL_CONFIG["magnitude_threshold"]))

# def _score_direction_inconsistency(flows):
#     angles = [np.arctan2(f[...,1], f[...,0]).mean() for f in flows]
#     if len(angles) < 2: return 0.5
#     diffs = [abs(angles[i+1] - angles[i]) for i in range(len(angles)-1)]
#     return float(min(1.0, float(np.mean(diffs)) / (TEMPORAL_CONFIG["direction_threshold"] * np.pi)))

# def _score_frame_difference(frames):
#     diffs = [np.abs(frames[i].astype(float) - frames[i+1].astype(float)).mean()
#              for i in range(len(frames)-1)]
#     if not diffs: return 0.5
#     return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["diff_threshold"]))

# def _score_texture_consistency(frames):
#     def lbp(frame):
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         lbp  = np.zeros_like(gray, dtype=np.uint8)
#         for i in range(8):
#             a = 2 * np.pi * i / 8
#             dx, dy = int(round(np.cos(a))), int(round(np.sin(a)))
#             shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
#             lbp += (shifted >= gray).astype(np.uint8) * (2**i)
#         hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0,256))
#         hist = hist.astype(float); hist /= hist.sum() + 1e-8
#         return hist
#     hists = [lbp(f) for f in frames]
#     diffs = [np.abs(hists[i] - hists[i+1]).sum() for i in range(len(hists)-1)]
#     if not diffs: return 0.5
#     return float(min(1.0, np.mean(diffs) / TEMPORAL_CONFIG["texture_threshold"]))

# def _score_edge_consistency(frames):
#     def edge(frame):
#         gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         edges = cv2.Canny(gray, 50, 150)
#         return edges.astype(float) / 255.0
#     edges = [edge(f) for f in frames]
#     diffs = [np.abs(edges[i] - edges[i+1]).mean() for i in range(len(edges)-1)]
#     if not diffs: return 0.5
#     return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["edge_threshold"]))

# def _analyze_temporal(segments: list[list[np.ndarray]], **kwargs) -> AnalyzerResult:
#     """광류 기반 5가지 지표로 프레임 간 시간적 불일치 측정 (현재 가중치 0으로 비활성)"""
#     if not segments:
#         return AnalyzerResult(score=0.5, status="skip", reason="시공간: 분석할 프레임 없음")

#     w = TEMPORAL_CONFIG["flow_weights"]
#     seg_scores = []
#     for seg_frames in segments:
#         if len(seg_frames) < 2: continue
#         flows = [_compute_optical_flow(seg_frames[i], seg_frames[i+1])
#                  for i in range(len(seg_frames)-1)]
#         s_mag  = _score_magnitude_inconsistency(flows)
#         s_dir  = _score_direction_inconsistency(flows)
#         s_diff = _score_frame_difference(seg_frames)
#         s_tex  = _score_texture_consistency(seg_frames)
#         s_edge = _score_edge_consistency(seg_frames)
#         seg_scores.append({
#             "score": (s_mag*w["magnitude_inconsistency"] + s_dir*w["direction_inconsistency"] +
#                       s_diff*w["frame_difference"] + s_tex*w["texture_consistency"] +
#                       s_edge*w["edge_consistency"]),
#             "mag": s_mag, "dir": s_dir, "diff": s_diff, "tex": s_tex, "edge": s_edge,
#         })

#     if not seg_scores:
#         return AnalyzerResult(score=0.5, status="skip", reason="시공간: 유효한 구간 없음")

#     final_score = float(np.mean([s["score"] for s in seg_scores]))
#     best = max(seg_scores, key=lambda x: x["score"])
#     return AnalyzerResult(
#         score=final_score, status="ok",
#         reason=(f"시공간: 이동불일치={best['mag']:.3f}, 방향불일치={best['dir']:.3f}, "
#                 f"프레임차분={best['diff']:.3f}, 텍스처={best['tex']:.3f}, 엣지={best['edge']:.3f} "
#                 f"(구간 {len(seg_scores)}개 평균)"),
#         detail={"segments": seg_scores},
    )


# ── 분석기 Registry ───────────────────────────────────────────

ANALYZER_MAP = {
    "clip":      _analyze_clip,
    "frequency": _analyze_frequency,
    "metadata":  _analyze_metadata,
#     "temporal":  _analyze_temporal,
    # Phase B: "rppg":    _analyze_rppg,    (얼굴 혈류 신호 감지)
#     # Phase C: "physics": _analyze_physics, (물리 일관성 — temporal 대체 예정)
}

# 타겟별 추가 분석기 매핑
# 기본 분석기(ANALYZERS) 전체 실행 후 타겟에 맞는 분석기를 추가로 append
# 추가 분석기는 config.py에서 가중치 0으로 설정 → 완성 후 가중치 올리면 활성화
TARGET_EXTRA_MAP = {
    "face":       ["rppg"],     # 얼굴 — Phase B: 혈류 신호 감지 (미완성)
    "background": ["fft_deep"], # 배경 — MediaPipe 배경 크롭 후 활성화 예정
    "motion":     ["physics"],  # 움직임 — Phase C: 물리 일관성 감지 (미완성)
    "voice":      ["audio"],    # 음성 — 추후 추가 예정
}

ANALYZER_STATUS_MAP = {
    "clip":      {"state": "ANALYZING_CLIP",      "status": "analyzing_clip",      "message": "프레임 유사도 기반 분석을 진행하는 중입니다."},
    "frequency": {"state": "ANALYZING_FREQUENCY", "status": "analyzing_frequency", "message": "주파수 기반 영상 흔적을 분석하는 중입니다."},
    "metadata":  {"state": "ANALYZING_METADATA",  "status": "analyzing_metadata",  "message": "영상 메타데이터를 분석하는 중입니다."},
#     "temporal":  {"state": "ANALYZING_TEMPORAL",  "status": "analyzing_temporal",  "message": "프레임 간 움직임 일관성을 분석하는 중입니다."},
}


def _select_analyzers(targets=None) -> list[str]:
    """
    타겟 유무에 따라 실행할 분석기 목록 반환.

    타겟 없음: 기본 분석기(ANALYZERS) 전체 실행
    타겟 있음: 기본 분석기 전체 + 타겟에 맞는 추가 분석기 append
              추가 분석기는 config.py에서 가중치 0 → 완성 후 가중치 올리면 활성화

    지원 타겟: face(얼굴), background(배경), motion(움직임), voice(음성)
    """
    selected = list(ANALYZERS)  # 기본 분석기 항상 전체 실행

    if not targets:
        return selected

    for target in targets:
        extra = TARGET_EXTRA_MAP.get(target, [])
        for analyzer in extra:
            # ANALYZER_MAP에 등록된 분석기만 추가 (미완성 분석기 방지)
            if analyzer in ANALYZER_MAP and analyzer not in selected:
                selected.append(analyzer)

    return selected


# ── 앙상블 ───────────────────────────────────────────────────

def _ensemble(results: dict[str, AnalyzerResult]) -> float:
    """
    가중치 기반 앙상블.
    error/skip 모듈은 제외하고 정상 모듈만 가중 평균.
    모든 모듈이 실패하면 0.5(중립) 대신 에러 처리를 위해 None 반환 후
    호출부에서 처리하도록 설계.
    """
    weighted_sum = total_weight = 0.0
    for name, result in results.items():
        if result.status != "ok":
            continue
        weight = ANALYZER_WEIGHTS.get(name, 0.0)
        weighted_sum += result.score * weight
        total_weight += weight

    # 정상 모듈이 하나도 없으면 None 반환 (호출부에서 에러 처리)
    if total_weight == 0:
        return None

    return float(np.clip(weighted_sum / total_weight, 0.0, 1.0))


# _get_video_duration 제거
# _validate_video에서 duration을 함께 반환하므로 중복 계산 불필요


# ── 백엔드 호출 진입점 ────────────────────────────────────────

def run_ai_video_analysis(
    video_path: str,
    output_dir: str,
    targets=None,
    progress_callback=None,
) -> dict:
    """
    [백엔드 호출용 핵심 함수 — 이름/인자 변경 금지]

    Args:
        video_path       : 분석할 영상 절대 경로
        output_dir       : 증거 프레임 저장 폴더
        targets          : 분석 대상 목록 (현재 보류 중 — None 사용 권장)
        progress_callback: 진행 상황 콜백 (없으면 무시)
    """
    try:
        # ── 0. 입력 검증 ──────────────────────────────────────
        _emit_progress(progress_callback, "VALIDATING", "validating", 5,
                       "영상 파일 형식과 길이를 확인하는 중입니다.")
        status, msg, duration = _validate_video(video_path)
        if status == "REJECT":
            return {"status": "error", "message": msg}

        # ── 1. 프레임 추출 ────────────────────────────────────
        _emit_progress(progress_callback, "EXTRACTING_FRAMES", "extracting_frames", 15,
                       "분석용 대표 프레임을 추출하는 중입니다.")
        frames, timestamps = extract_frames(video_path)
        if not frames:
            return {"status": "error", "message": "프레임 추출 실패"}

#         # ── 2. 시공간 프레임 추출 ─────────────────────────────
#         _emit_progress(progress_callback, "EXTRACTING_TEMPORAL", "extracting_temporal", 25,
#                        "시공간 분석용 프레임 구간을 추출하는 중입니다.")
#         temporal_segments = extract_temporal_frames(video_path)

        # ── 3. 영상 타입 판별 (미래 분기용) ──────────────────
        # 반드시 변수에 받을 것 — Phase B, C에서 실제로 사용 예정
        video_type = _detect_video_type(video_path, frames)

        # ── 4. 분석기 실행 ────────────────────────────────────
        analyzer_arg_map = {
            "clip":      {"frames": frames},
            "frequency": {"frames": frames},
            "metadata":  {"video_path": video_path},
#             "temporal":  {"segments": temporal_segments},
        }

        selected_analyzers = _select_analyzers(targets)
        results: dict[str, AnalyzerResult] = {}
        total_analyzers = len(selected_analyzers)

        for index, name in enumerate(selected_analyzers):
            analyzer_status = ANALYZER_STATUS_MAP.get(name, {
                "state": "ANALYZING", "status": f"analyzing_{name}",
                "message": f"{name} 분석을 진행하는 중입니다.",
            })
            # 분석기 실행 구간을 25~75%로 균등 분배
            progress = 25 + int(((index + 1) / total_analyzers) * 50)
            _emit_progress(progress_callback,
                           analyzer_status["state"], analyzer_status["status"],
                           progress, analyzer_status["message"], selected_analyzers)

            fn = ANALYZER_MAP.get(name)
            if fn is None:
                continue
            try:
                results[name] = fn(**analyzer_arg_map.get(name, {}))
            except Exception as e:
                results[name] = AnalyzerResult(score=0.5, status="error",
                                               reason=f"{name} 오류: {e}")

        # ── 5. 앙상블 ─────────────────────────────────────────
        final_score = _ensemble(results)

        # 모든 분석기 실패 시 에러 반환 (0.5 오판 방지)
        if final_score is None:
            return {"status": "error", "message": "모든 분석기 실패 — 영상을 분석할 수 없습니다."}

        # ── 6. 증거 프레임 저장 ───────────────────────────────
        # AI 의심도 높은 프레임 순서로 정렬
        sorted_ts = timestamps
        probabilities = None
        clip_result = results.get("clip")
        if clip_result and clip_result.status == "ok":
            similarities = clip_result.detail.get("similarities", [])
            if similarities and len(similarities) == len(timestamps) - 1:
                ts_prob_pairs = sorted(
                    [(ts, 1.0 - sim) for ts, sim in zip(timestamps[:-1], similarities)],
                    key=lambda x: x[1], reverse=True
                )
                sorted_ts     = [ts for ts, _ in ts_prob_pairs]
                probabilities = [prob for _, prob in ts_prob_pairs]

        _emit_progress(progress_callback, "SAVING_EVIDENCE", "saving_evidence", 80,
                       "분석 근거 프레임을 저장하는 중입니다.", selected_analyzers)
        evidence_frames = save_evidence_frames(
            video_path=video_path, output_dir=output_dir,
            timestamps=sorted_ts, probabilities=probabilities, top_n=3,
        )

        # ── 7. 결과 조립 ──────────────────────────────────────
        _emit_progress(progress_callback, "BUILDING_RESULT", "building_result", 90,
                       "최종 분석 결과를 생성하는 중입니다.", selected_analyzers)
        result_json = build_result_json(
            final_score=final_score, results=results,
            weights=ANALYZER_WEIGHTS, evidence_frames=evidence_frames,
        )
        result_json["duration"]           = duration  # _validate_video에서 계산한 값 재사용
        result_json["selected_targets"]   = targets or []
        result_json["selected_analyzers"] = selected_analyzers

        _emit_progress(progress_callback, "DONE", "done", 100,
                       "분석이 완료되었습니다.", selected_analyzers)

        return result_json

    except Exception:
        return {"status": "error", "message": f"분석 중 예외 발생:\n{traceback.format_exc()}"}
