import { useEffect, useState }                 from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { addHistory }                          from "../utils/history";
import { getVerdict, VERDICT_CONFIG }          from "../constants/verdict";
import usePollResult                           from "../hooks/usePollResult";
import { ErrorMessage }                        from "../components/common";
import { VerdictBanner, ConfidenceGauge,
         AnalysisTimeline, AnalysisTable,
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
  const frames      = result.evidence_frames  || [];
  const duration    = result.duration
    || (frames.length > 0 ? Math.ceil(frames[frames.length - 1].timestamp * 1.3) : 60);

  return (
    <main className="max-w-content mx-auto px-fluid-md py-fluid-lg">
      <VerdictBanner   cfg={cfg} />
      <ConfidenceGauge probability={probability} cfg={cfg} />
      {frames.length > 0 && <AnalysisTimeline frames={frames} duration={duration} taskId={taskId} />}
      <AnalysisTable   scores={details.analyzer_scores} />
      <ShareCard />
      <button className="btn-ghost" onClick={() => navigate("/")}>
        ← 다른 영상 분석하기
      </button>
    </main>
  );
}