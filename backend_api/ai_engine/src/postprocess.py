"""
ai_engine/src/postprocess.py

분석 완료 후 결과물을 만드는 후처리 전담 모듈. (신규 파일)

[존재 이유]
  v1에서 save_evidence_frames()가 preprocess.py에 있었습니다.
  전처리(프레임 추출)와 후처리(결과 저장)는 역할이 다르므로 분리합니다.

  이 파일의 역할:
    1. 분석 결과를 바탕으로 evidence 프레임을 디스크에 저장
    2. 백엔드에 반환할 최종 JSON 구조를 조립

[이 파일을 쓰는 곳]
  inference.py의 run_ai_video_analysis() 마지막 단계에서 호출합니다.
"""

import os
import cv2
import numpy as np
from ai_engine.src.config import RISK_THRESHOLDS, RELIABILITY_UNCERTAIN_RANGE
from ai_engine.src.base import AnalyzerResult


def save_evidence_frames(
    video_path: str,
    output_dir: str,
    timestamps: list[float],
    top_n: int = 3,
) -> list[dict]:
    """
    AI 판정 근거로 보여줄 프레임을 파일로 저장합니다.

    어떤 프레임을 저장하는가:
      CLIP 분석기가 "이 프레임이 AI 같다"고 판단한 점수가 높은 순서대로
      timestamps가 정렬되어 넘어옵니다.
      그 중 top_n개만 저장합니다.

    파일명 규칙: frame_{초단위}.jpg
      예: frame_5.2.jpg (5.2초 지점 프레임)

    Args:
        video_path : 원본 영상 경로
        output_dir : 저장 폴더 경로 (없으면 자동 생성)
        timestamps : 저장할 프레임의 타임스탬프 목록 (점수 높은 순 정렬 권장)
        top_n      : 저장할 프레임 수

    Returns:
        [{"timestamp": 5.2, "file_name": "frame_5.2.jpg"}, ...]
        빈 리스트 반환 시 evidence 없음으로 처리됩니다.
    """
    os.makedirs(output_dir, exist_ok=True)

    cap          = cv2.VideoCapture(video_path)
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    evidence = []
    for ts in timestamps[:top_n]:
        frame_idx = min(int(ts * fps), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        file_name = f"frame_{ts}.jpg"
        save_path = os.path.join(output_dir, file_name)
        cv2.imwrite(save_path, frame)
        evidence.append({"timestamp": ts, "file_name": file_name})

    cap.release()
    return evidence


def build_result_json(
    final_score: float,
    results: dict[str, "AnalyzerResult"],
    weights: dict[str, float],
    evidence_frames: list[dict],
) -> dict:
    """
    백엔드에 반환할 최종 JSON을 조립합니다.

    [반환 구조 설명]
      is_ai       : confidence가 AI_THRESHOLD(0.5) 이상이면 True
      confidence  : 0~1 실수. 앙상블 가중 평균.
      risk_level  : "HIGH" / "MEDIUM" / "LOW"
                    프론트에서 색상/아이콘 표시에 사용.
      reliability : "low"    → 0.45~0.55 구간, 모델이 확신 못하는 경계
                    "normal" → 그 외, 판정 신뢰 가능
      module_scores: 각 분석기별 점수. 프론트 시각화 근거 표시에 사용.
      analysis_details.details: 사람이 읽을 수 있는 판정 요약문
      evidence_frames: AI 의심 근거 프레임 파일 정보

    Args:
        final_score    : 앙상블 최종 점수
        results        : 분석기 이름 → AnalyzerResult 딕셔너리
        weights        : 분석기 이름 → 가중치 딕셔너리 (config.ANALYZER_WEIGHTS)
        evidence_frames: save_evidence_frames() 반환값

    Returns:
        백엔드 반환용 dict
    """
    from ai_engine.src.config import AI_THRESHOLD

    is_ai      = final_score >= AI_THRESHOLD
    risk       = _risk_level(final_score)
    reliability = _reliability(final_score)

    # module_scores: 각 모듈 점수 + 가중치 + 상태
    module_scores = {}
    for name, result in results.items():
        module_scores[name] = {
            **result.to_summary(),
            "weight": weights.get(name, 0.0),
        }

    # 판정 근거 문자열 조합 (status가 "ok"인 모듈만 포함)
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

    return {
        "status":      "success",
        "is_ai":       bool(is_ai),
        "confidence":  round(final_score, 4),
        #"risk_level":  risk,           # v2 추가 — 프론트 색상/아이콘 표시용
        #"reliability": reliability,    # v2 추가 — 경계 케이스 경고용
        #"module_scores": module_scores, # v2 추가 — 프론트 근거 시각화용
        "analysis_details": {
            "details":          details_str,
            "detected_regions": [],    # 미래: 얼굴/객체 영역 좌표 (현재 미사용)
        },
        "evidence_frames": evidence_frames,
    }


# ── 내부 헬퍼 함수 ─────────────────────────────────────────────────────────

def _risk_level(score: float) -> str:
    """
    confidence 점수를 3단계 위험도로 변환합니다.
    기준값은 config.RISK_THRESHOLDS에서 관리합니다.
    """
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _reliability(score: float) -> str:
    """
    모델이 경계 케이스에서 판단을 얼마나 확신하는지 나타냅니다.

    0.45~0.55 구간은 AI / 실제 어느 쪽도 확실히 아닌 경계입니다.
    프론트에서 "판단이 불확실합니다" 경고를 띄울 때 사용합니다.
    """
    lo, hi = RELIABILITY_UNCERTAIN_RANGE
    if lo < score < hi:
        return "low"
    return "normal"
