import { useEffect, useState }                 from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { addHistory }                          from "../utils/history";
import { getVerdict, VERDICT_CONFIG }          from "../constants/verdict";
import usePollResult                           from "../hooks/usePollResult";
import { ErrorMessage }                        from "../components/common";
import { VerdictBanner, ConfidenceGauge,
         AnalysisTimeline, AnalysisTable,
         AnalysisChart,
         ShareCard, AnalyzingScreen }          from "../components/result";

export default function ResultPage() {
  const navigate  = useNavigate();
  const { taskId }= useParams();
  const location  = useLocation();

  const fileName    = location.state?.name        || taskId;
  const targets     = location.state?.targets     || [];
  const fromHistory = location.state?.fromHistory || false;
  const initialResult = location.state?.result    || null;  // 기록에서 넘어온 결과

  const { result, taskStatus, message, error } = usePollResult(taskId, { initialResult });
  const [saved, setSaved] = useState(fromHistory); // 기록에서 온 경우 재저장 방지

  useEffect(() => {
    if (result && !saved && !fromHistory) {
      addHistory({ taskId, name: fileName, apiResult: result });
      window.dispatchEvent(new Event("history-updated"));
      setSaved(true);
    }
  }, [result, saved, fromHistory, taskId, fileName]);

  if (error) return (
    <main className="max-w-content mx-auto px-fluid-md py-fluid-lg">
      <ErrorMessage message={error} />
      <button className="btn-ghost mt-fluid-sm" onClick={() => navigate("/")}>
        ← 홈으로 돌아가기
      </button>
    </main>
  );

  if (!result) return (
    <main className="max-w-content mx-auto px-fluid-md py-fluid-lg">
      <AnalyzingScreen taskStatus={taskStatus} message={message} targets={targets} />
    </main>
  );

  const probability = Math.round((result.confidence || 0) * 100);
  const cfg         = VERDICT_CONFIG[getVerdict(result.confidence || 0)];
  const details     = result.analysis_details || {};
  const moduleScores = result.module_scores || null;
  const frames      = result.evidence_frames  || [];
  const duration    = result.duration
    || (frames.length > 0 ? Math.ceil(frames[frames.length - 1].timestamp * 1.3) : 60);

  return (
    <main className="max-w-content mx-auto px-fluid-md py-fluid-lg">
      <VerdictBanner   cfg={cfg} />
      <ConfidenceGauge probability={probability} cfg={cfg} />
      {frames.length > 0 && <AnalysisTimeline frames={frames} duration={duration} taskId={taskId} />}

      {/* ── 분석 모듈 차트 ────────────────────────────────────────────
          [현재] module_scores가 백엔드에서 내려오지 않아 임시 데이터 사용.
                 postprocess.py의 build_result_json()에 module_scores를 추가하면
                 자동으로 실제 데이터로 전환됩니다.
          [TODO] 백엔드 연동 완료 후 isFallback prop 및 임시 데이터 로직 제거 */}
      <AnalysisChart
        moduleScores={moduleScores}           // 실제 데이터 (백엔드 postprocess.py에 module_scores 추가 후 채워짐)
        confidence={result.confidence ?? 0}   // 임시 점수 생성용 fallback
        detailsStr={details.details}          // 근거 문자열 파싱용 (module_scores 없을 때 사용)
      />

      {/* 기존 AnalysisTable — 백엔드 연동 완료 후 제거 가능 */}
      <AnalysisTable scores={details.analyzer_scores} moduleScores={moduleScores} details={details.details} />
      <ShareCard />
      <button className="btn-ghost" onClick={() => navigate("/")}>
        ← 다른 영상 분석하기
      </button>
    </main>
  );
}