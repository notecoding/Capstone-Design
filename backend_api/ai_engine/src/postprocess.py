import os
import cv2
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
    evidence = []

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        for i, ts in enumerate(timestamps[:top_n]):
            frame_idx = min(int(ts * fps), total_frames - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                continue

            # 파일명에 점(.) 포함 시 일부 서버에서 문제 발생 방지
            safe_ts = str(round(float(ts), 2)).replace(".", "_")
            file_name = f"frame_{safe_ts}.jpg"
            save_path = os.path.join(output_dir, file_name)
            cv2.imwrite(save_path, frame)

            prob = None
            if probabilities and i < len(probabilities):
                prob = round(float(probabilities[i]), 4)

            image_url = _build_storage_url(save_path)

            evidence.append({
                "timestamp": round(float(ts), 2),
                "time":      round(float(ts), 2),
                "file_name": file_name,
                "image_url": image_url,
                "probability": prob,
                "score":     prob if prob is not None else 0,
                "reason":    "AI 조작 가능성이 높은 구간으로 선택된 증거 프레임입니다.",
                "tags":      []
            })

    finally:
        cap.release()  # 에러 발생해도 항상 파일 핸들 해제

    return evidence


def build_result_json(
    final_score: float,
    results: dict,
    weights: dict[str, float],
    evidence_frames: list[dict],
) -> dict:

    from ai_engine.src.config import AI_THRESHOLD

    is_ai       = final_score >= AI_THRESHOLD
    risk        = _risk_level(final_score)
    reliability = _reliability(final_score)

    module_scores = _build_module_scores(results)
    details       = _build_module_details(results, weights)

    ok_reasons = [
        r.reason for r in results.values()
        if r.status == "ok" and r.reason
    ]

    level_msg = {
        "HIGH":   "AI 생성 영상으로 판별되었습니다.",
        "MEDIUM": "AI 생성 가능성이 있으나 확실하지 않습니다.",
        "LOW":    "실제 촬영 영상으로 판별되었습니다.",
    }[risk]

    details_str = level_msg
    if ok_reasons:
        details_str += " 근거: " + " / ".join(ok_reasons)

    normalized_evidence_frames = _normalize_evidence_frames(evidence_frames)

    return {
        "status":        "success",
        "is_ai":         bool(is_ai),
        "confidence":    round(float(final_score), 4),
        "overall_score": round(float(final_score), 4),
        "label":         _label_from_risk(risk),
        "risk":          risk,
        "reliability":   reliability,
        "summary":       level_msg,
        "module_scores": module_scores,
        "details":       details,
        "analysis_details": {
            "details":          details_str,
            "detected_regions": [],
        },
        "evidence_frames": normalized_evidence_frames,
    }


def _build_module_scores(results: dict) -> dict:
    return {
        name: round(float(result.score), 4)
        for name, result in results.items()
    }


def _build_module_details(results: dict, weights: dict[str, float]) -> list[dict]:
    details = []
    for name, result in results.items():
        score = round(float(result.score), 4)
        risk  = _risk_level(score)
        details.append({
            "module":      name,
            "module_name": _module_display_name(name),
            "score":       score,
            "label":       _label_from_risk(risk),
            "risk":        risk,
            "status":      result.status,
            "weight":      weights.get(name, 0.0),
            "description": _module_description(name, score, result.status),
            "reason":      result.reason,
        })
    return details


def _normalize_evidence_frames(evidence_frames: list[dict]) -> list[dict]:
    normalized = []
    for frame in evidence_frames:
        timestamp   = frame.get("timestamp", frame.get("time", 0))
        file_name   = frame.get("file_name", "")
        probability = frame.get("probability", frame.get("score", None))
        image_url   = frame.get("image_url", "")

        if not image_url and file_name:
            image_url = _build_storage_url(file_name)

        normalized.append({
            "timestamp":   timestamp,
            "time":        timestamp,
            "file_name":   file_name,
            "image_url":   image_url,
            "probability": probability,
            "score":       probability if probability is not None else 0,
            "reason":      frame.get("reason", "AI 조작 가능성이 높은 구간으로 선택된 증거 프레임입니다."),
            "tags":        frame.get("tags", [])
        })
    return normalized


def _build_storage_url(path: str) -> str:
    normalized_path = path.replace("\\", "/")
    if normalized_path.startswith("/storage/"):
        return normalized_path
    if normalized_path.startswith("storage/"):
        return "/" + normalized_path
    storage_index = normalized_path.find("storage/")
    if storage_index != -1:
        return "/" + normalized_path[storage_index:]
    return normalized_path


def _module_display_name(module: str) -> str:
    names = {
        "clip":      "프레임 유사도",
        "frequency": "주파수 분석",
        "metadata":  "메타데이터",
        "temporal":  "시공간 움직임",
        "rppg":      "얼굴 혈류 신호",
        "fft_deep":  "주파수 심화",
        "physics":   "물리 일관성",
        "audio":     "음성",
    }
    return names.get(module, module)


def _module_description(module: str, score: float, status: str) -> str:
    module_name = _module_display_name(module)
    if status != "ok":
        return f"{module_name} 분석이 정상적으로 완료되지 않았습니다."
    risk = _risk_level(score)
    if risk == "HIGH":
        return f"{module_name} 영역에서 AI 조작 가능성이 높게 감지되었습니다."
    if risk == "MEDIUM":
        return f"{module_name} 영역에서 일부 의심 요소가 감지되었습니다."
    return f"{module_name} 영역에서 뚜렷한 조작 흔적이 감지되지 않았습니다."


def _label_from_risk(risk: str) -> str:
    if risk == "HIGH":   return "위험"
    if risk == "MEDIUM": return "주의"
    return "정상"


def _risk_level(score: float) -> str:
    if score >= RISK_THRESHOLDS["HIGH"]:   return "HIGH"
    if score >= RISK_THRESHOLDS["MEDIUM"]: return "MEDIUM"
    return "LOW"


def _reliability(score: float) -> str:
    lo, hi = RELIABILITY_UNCERTAIN_RANGE
    if lo < score < hi:
        return "low"
    return "normal"
