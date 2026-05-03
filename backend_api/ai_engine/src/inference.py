import os
import subprocess
import json
import traceback
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ai_engine.src.base import AnalyzerResult
from ai_engine.src.config import (
    ANALYZERS, ANALYZER_WEIGHTS,
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


def _detect_video_type(video_path: str, frames: list[np.ndarray]) -> dict:
    return {
        "has_face": False,
        "is_short": False,
        "is_compressed": False,
    }


def _validate_video(video_path: str) -> tuple[str, str]:
    if not os.path.exists(video_path):
        return "REJECT", f"파일 없음: {video_path}"

    ext = Path(video_path).suffix.lower()
    if ext not in VIDEO_CONFIG["supported_formats"]:
        return "REJECT", f"지원하지 않는 형식: {ext}"

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    duration = n_frames / fps if fps > 0 else 0

    if duration < VIDEO_CONFIG["min_duration"]:
        return "REJECT", f"영상이 너무 짧음 ({duration:.1f}초 — 최소 {VIDEO_CONFIG['min_duration']}초 필요)"

    if duration > VIDEO_CONFIG["max_duration"]:
        return "REJECT", f"영상이 너무 긺 ({duration:.0f}초 — 최대 {VIDEO_CONFIG['max_duration']}초)"

    return "OK", ""


_clip_model = None
_clip_preprocess = None


def _load_clip():
    global _clip_model, _clip_preprocess

    if _clip_model is not None:
        return

    import open_clip

    device = CLIP_CONFIG["device"]
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        CLIP_CONFIG["model_name"],
        pretrained=CLIP_CONFIG["pretrained"],
        device=device,
    )
    _clip_model.eval()


def _analyze_clip(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    import torch

    _load_clip()
    device = CLIP_CONFIG["device"]

    frame_feats = []

    for frame in frames:
        rgb = frame[:, :, ::-1]
        pil_img = Image.fromarray(rgb.astype(np.uint8))
        tensor = _clip_preprocess(pil_img).unsqueeze(0).to(device)

        with torch.no_grad():
            feat = _clip_model.encode_image(tensor)
            feat = feat / feat.norm(dim=-1, keepdim=True)

        frame_feats.append(feat)

    if len(frame_feats) < 2:
        return AnalyzerResult(
            score=0.5,
            status="skip",
            reason="CLIP: 프레임 수 부족 (2개 미만)",
        )

    similarities = []

    for i in range(len(frame_feats) - 1):
        sim = (frame_feats[i] @ frame_feats[i + 1].T).item()
        similarities.append(sim)

    avg_sim = float(np.mean(similarities))
    std_sim = float(np.std(similarities))
    score = float(np.clip(1.0 - avg_sim, 0.0, 1.0))

    return AnalyzerResult(
        score=score,
        status="ok",
        reason=f"CLIP: 프레임 간 평균 유사도 {avg_sim:.3f} (낮을수록 AI 의심)",
        detail={
            "avg_similarity": avg_sim,
            "std_similarity": std_sim,
            "similarities": similarities,
            "n_frames_analyzed": len(frame_feats),
        },
    )


def _analyze_frequency(frames: list[np.ndarray], **kwargs) -> AnalyzerResult:
    threshold = FREQUENCY_CONFIG["high_freq_threshold"]
    all_hf, all_rv, all_da = [], [], []

    for frame in frames:
        gray = np.mean(frame, axis=2)
        fft_shift = np.fft.fftshift(np.fft.fft2(gray))
        mag = np.log1p(np.abs(fft_shift))
        h, w = mag.shape
        cx, cy = w // 2, h // 2

        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        r = min(h, w) // 4

        lo = mag[dist <= r].sum()
        hi = mag[dist > r].sum()
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
    score = hf_score * 0.4 + rv_score * 0.4 + da_score * 0.2

    return AnalyzerResult(
        score=float(score),
        status="ok",
        reason=f"FFT: 고주파비={avg_hf:.3f}, 방사분산={avg_rv:.3f}, 방향비대칭={avg_da:.3f}",
        detail={
            "high_freq_ratio": avg_hf,
            "radial_variance": avg_rv,
            "directional_asymm": avg_da,
        },
    )


def _analyze_metadata(video_path: str, **kwargs) -> AnalyzerResult:
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
            encoding="utf-8",
            errors="ignore",
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except Exception as e:
        return AnalyzerResult(
            score=0.5,
            status="error",
            reason=f"ffprobe 실패: {e}",
        )

    if not data:
        return AnalyzerResult(
            score=0.5,
            status="skip",
            reason="메타데이터 없음",
        )

    fmt = data.get("format", {})
    streams = data.get("streams", [])
    tags = fmt.get("tags", {})

    components = []
    found_items = []

    encoder_str = " ".join([
        tags.get("encoder", ""),
        tags.get("comment", ""),
        tags.get("description", ""),
        fmt.get("format_long_name", ""),
    ]).lower()

    found_kw = [
        kw for kw in METADATA_CONFIG["suspicious_encoders"]
        if kw in encoder_str
    ]

    if found_kw:
        components.append(0.95)
        found_items.append(f"의심 인코더: {found_kw}")
    else:
        components.append(0.20)

    if any("c2pa" in str(v).lower() for v in tags.values()):
        components.append(0.90)
        found_items.append("C2PA AI 생성 마커 감지")
    else:
        components.append(0.25)

    video_streams = [s for s in streams if s.get("codec_type") == "video"]

    if video_streams:
        w = video_streams[0].get("width", 0)
        h = video_streams[0].get("height", 0)

        if (w, h) in METADATA_CONFIG["ai_resolutions"]:
            components.append(0.75)
            found_items.append(f"AI 전형 해상도: {w}x{h}")
        else:
            components.append(0.20)

    score = float(np.mean(components)) if components else 0.5
    reason = " | ".join(found_items) if found_items else "메타데이터 이상 없음"

    return AnalyzerResult(
        score=score,
        status="ok",
        reason=reason,
        detail={"found_items": found_items},
    )


def _compute_optical_flow(f1: np.ndarray, f2: np.ndarray) -> np.ndarray:
    g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)

    return cv2.calcOpticalFlowFarneback(
        g1,
        g2,
        None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )


def _score_magnitude_inconsistency(flows: list[np.ndarray]) -> float:
    mags = [
        np.sqrt(f[..., 0] ** 2 + f[..., 1] ** 2).mean()
        for f in flows
    ]

    if len(mags) < 2:
        return 0.5

    return float(min(1.0, np.std(mags) / TEMPORAL_CONFIG["magnitude_threshold"]))


def _score_direction_inconsistency(flows: list[np.ndarray]) -> float:
    angles = [
        np.arctan2(f[..., 1], f[..., 0]).mean()
        for f in flows
    ]

    if len(angles) < 2:
        return 0.5

    diffs = [
        abs(angles[i + 1] - angles[i])
        for i in range(len(angles) - 1)
    ]

    avg_diff = float(np.mean(diffs))

    return float(min(1.0, avg_diff / (TEMPORAL_CONFIG["direction_threshold"] * np.pi)))


def _score_frame_difference(frames: list[np.ndarray]) -> float:
    diffs = [
        np.abs(frames[i].astype(float) - frames[i + 1].astype(float)).mean()
        for i in range(len(frames) - 1)
    ]

    if not diffs:
        return 0.5

    return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["diff_threshold"]))


def _score_texture_consistency(frames: list[np.ndarray]) -> float:
    def lbp_histogram(frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        n_points = 8
        lbp = np.zeros_like(gray, dtype=np.uint8)

        for i in range(n_points):
            angle = 2 * np.pi * i / n_points
            dx = int(round(np.cos(angle)))
            dy = int(round(np.sin(angle)))
            shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
            lbp += (shifted >= gray).astype(np.uint8) * (2 ** i)

        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist = hist.astype(float)
        hist /= hist.sum() + 1e-8

        return hist

    hists = [lbp_histogram(f) for f in frames]
    diffs = [
        np.abs(hists[i] - hists[i + 1]).sum()
        for i in range(len(hists) - 1)
    ]

    if not diffs:
        return 0.5

    return float(min(1.0, np.mean(diffs) / TEMPORAL_CONFIG["texture_threshold"]))


def _score_edge_consistency(frames: list[np.ndarray]) -> float:
    def edge_map(frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
        return edges.astype(float) / 255.0

    edges = [edge_map(f) for f in frames]
    diffs = [
        np.abs(edges[i] - edges[i + 1]).mean()
        for i in range(len(edges) - 1)
    ]

    if not diffs:
        return 0.5

    return float(min(1.0, np.std(diffs) / TEMPORAL_CONFIG["edge_threshold"]))


def _analyze_temporal(segments: list[list[np.ndarray]], **kwargs) -> AnalyzerResult:
    if not segments:
        return AnalyzerResult(
            score=0.5,
            status="skip",
            reason="시공간: 분석할 프레임 없음",
        )

    w = TEMPORAL_CONFIG["flow_weights"]
    seg_scores = []

    for seg_frames in segments:
        if len(seg_frames) < 2:
            continue

        flows = [
            _compute_optical_flow(seg_frames[i], seg_frames[i + 1])
            for i in range(len(seg_frames) - 1)
        ]

        s_mag = _score_magnitude_inconsistency(flows)
        s_dir = _score_direction_inconsistency(flows)
        s_diff = _score_frame_difference(seg_frames)
        s_tex = _score_texture_consistency(seg_frames)
        s_edge = _score_edge_consistency(seg_frames)

        seg_score = (
            s_mag * w["magnitude_inconsistency"] +
            s_dir * w["direction_inconsistency"] +
            s_diff * w["frame_difference"] +
            s_tex * w["texture_consistency"] +
            s_edge * w["edge_consistency"]
        )

        seg_scores.append({
            "score": seg_score,
            "mag": s_mag,
            "dir": s_dir,
            "diff": s_diff,
            "tex": s_tex,
            "edge": s_edge,
        })

    if not seg_scores:
        return AnalyzerResult(
            score=0.5,
            status="skip",
            reason="시공간: 유효한 구간 없음",
        )

    final_score = float(np.mean([s["score"] for s in seg_scores]))
    best = max(seg_scores, key=lambda x: x["score"])

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


ANALYZER_MAP = {
    "clip": _analyze_clip,
    "frequency": _analyze_frequency,
    "metadata": _analyze_metadata,
    "temporal": _analyze_temporal,
}


def _ensemble(results: dict[str, AnalyzerResult]) -> float:
    weighted_sum = 0.0
    total_weight = 0.0

    for name, result in results.items():
        if result.status != "ok":
            continue

        weight = ANALYZER_WEIGHTS.get(name, 0.0)
        weighted_sum += result.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.5

    return float(np.clip(weighted_sum / total_weight, 0.0, 1.0))


def _get_video_duration(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    if fps <= 0:
        return 0.0

    return round(total_frames / fps, 2)


def run_ai_video_analysis(video_path: str, output_dir: str) -> dict:
    try:
        status, msg = _validate_video(video_path)

        if status == "REJECT":
            return {
                "status": "error",
                "message": msg,
            }

        frames, timestamps = extract_frames(video_path)

        if not frames:
            return {
                "status": "error",
                "message": "프레임 추출 실패",
            }

        temporal_segments = extract_temporal_frames(video_path)
        video_type = _detect_video_type(video_path, frames)

        analyzer_arg_map = {
            "clip": {"frames": frames},
            "frequency": {"frames": frames},
            "metadata": {"video_path": video_path},
            "temporal": {"segments": temporal_segments},
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
                    score=0.5,
                    status="error",
                    reason=f"{name} 오류: {e}",
                )

        final_score = _ensemble(results)

        sorted_ts = timestamps
        probabilities = None

        clip_result = results.get("clip")

        if clip_result and clip_result.status == "ok":
            similarities = clip_result.detail.get("similarities", [])

            if similarities and len(similarities) == len(timestamps) - 1:
                ts_prob_pairs = [
                    (ts, 1.0 - sim)
                    for ts, sim in zip(timestamps[:-1], similarities)
                ]

                ts_prob_pairs = sorted(
                    ts_prob_pairs,
                    key=lambda x: x[1],
                    reverse=True,
                )

                sorted_ts = [ts for ts, _ in ts_prob_pairs]
                probabilities = [prob for _, prob in ts_prob_pairs]

        evidence_frames = save_evidence_frames(
            video_path=video_path,
            output_dir=output_dir,
            timestamps=sorted_ts,
            probabilities=probabilities,
            top_n=3,
        )

        result_json = build_result_json(
            final_score=final_score,
            results=results,
            weights=ANALYZER_WEIGHTS,
            evidence_frames=evidence_frames,
        )

        result_json["duration"] = _get_video_duration(video_path)

        return result_json

    except Exception:
        return {
            "status": "error",
            "message": f"분석 중 예외 발생:\n{traceback.format_exc()}",
        }