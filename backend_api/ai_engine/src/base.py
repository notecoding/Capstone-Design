"""
ai_engine/src/base.py

분석기 표준 인터페이스 정의.

[존재 이유]
  기존 코드는 각 분석기가 반환하는 형태가 제각각이었습니다.
    _analyze_clip()      → (float, str, list[float])
    _analyze_frequency() → (float, str)
    _analyze_metadata()  → (float, str, list[dict])
    _analyze_temporal()  → (float, str)

  이 때문에 앙상블 함수와 결과 조합 함수가 모듈마다 다르게 처리해야 했고,
  새 분석기를 추가할 때마다 inference.py 전체를 수정해야 했습니다.

  AnalyzerResult 하나로 통일하면:
    - 앙상블 함수가 모든 모듈을 동일하게 처리 가능
    - 새 분석기 추가 시 inference.py 수정 불필요
    - 반환 JSON의 module_scores 구조가 자동으로 통일됨

[사용법]
  from ai_engine.src.base import AnalyzerResult

  def _analyze_something(frames) -> AnalyzerResult:
      ...
      return AnalyzerResult(
          score=0.87,
          status="ok",
          reason="프레임 간 불일치 감지",
          detail={"avg_similarity": 0.83, "std": 0.12},
      )
"""

from dataclasses import dataclass, field


@dataclass
class AnalyzerResult:
    """
    모든 분석기가 반환해야 하는 표준 결과 형식.

    Fields:
        score  : 0.0 ~ 1.0. 높을수록 AI 생성 의심.
        status : "ok"    → 분석 정상 완료
                 "error" → 분석 중 예외 발생
                 "skip"  → 해당 영상에 적용 불가 (예: 얼굴 없는데 rPPG 시도)
        reason : 판단 근거 한 줄 요약. 프론트 표시 및 로그용.
        detail : 모듈별 세부 수치. 형식 자유 (dict).
                 예: {"avg_similarity": 0.83, "frame_scores": [...]}
    """
    score:  float
    status: str
    reason: str
    detail: dict = field(default_factory=dict)

    def to_summary(self) -> dict:
        """
        반환 JSON의 module_scores 항목 하나를 생성합니다.
        inference.py의 결과 조합부에서 사용합니다.
        """
        return {
            "score":  round(self.score, 4),
            "status": self.status,
            "reason": self.reason,
        }