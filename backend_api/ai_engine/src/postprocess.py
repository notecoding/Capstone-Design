import os
import cv2
import numpy as np
from ai_engine.src.config import RISK_THRESHOLDS, RELIABILITY_UNCERTAIN_RANGE


def save_evidence_frames(
    video_path: str,
    output_dir: str,
    timestamps: list[float],
    probabilities: list[float] | None = None,
    top_n: int = 3,
) -> list[dict]:

    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    evidence = []

    for i, ts in enumerate(timestamps[:top_n]):
        frame_idx = min(int(ts * fps), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        file_name = f"frame_{ts}.jpg"
        save_path = os.path.join(output_dir, file_name)
        cv2.imwrite(save_path, frame)

        prob = None
        if probabilities and i < len(probabilities):
            prob = round(float(probabilities[i]), 4)

        evidence.append({
            "timestamp": ts,
            "file_name": file_name,
            "probability": prob
        })

    cap.release()
    return evidence


def build_result_json(
    final_score: float,
    results: dict,
    weights: dict[str, float],
    evidence_frames: list[dict],
) -> dict:

    from ai_engine.src.config import AI_THRESHOLD

    is_ai = final_score >= AI_THRESHOLD
    risk = _risk_level(final_score)
    reliability = _reliability(final_score)

    module_scores = {}
    for name, result in results.items():
        module_scores[name] = {
            **result.to_summary(),
            "weight": weights.get(name, 0.0),
        }

    ok_reasons = [
        r.reason for r in results.values()
        if r.status == "ok" and r.reason
    ]

    level_msg = {
        "HIGH": "AI 생성 영상으로 판별되었습니다.",
        "MEDIUM": "AI 생성 가능성이 있으나 확실하지 않습니다.",
        "LOW": "실제 촬영 영상으로 판별되었습니다.",
    }[risk]

    details_str = level_msg
    if ok_reasons:
        details_str += " 근거: " + " / ".join(ok_reasons)

    return {
        "status": "success",
        "is_ai": bool(is_ai),
        "confidence": round(final_score, 4),
        "analysis_details": {
            "details": details_str,
            "detected_regions": [],
        },
        "evidence_frames": evidence_frames,
    }


def _risk_level(score: float) -> str:
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _reliability(score: float) -> str:
    lo, hi = RELIABILITY_UNCERTAIN_RANGE
    if lo < score < hi:
        return "low"
    return "normal"