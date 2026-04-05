import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { analyzeService } from "../api/services";
import Loading from "../components/Loading";
import ErrorMessage from "../components/ErrorMessage";

function getVerdict(confidence) {
  if (confidence >= 0.7) return "danger";
  if (confidence >= 0.4) return "warning";
  return "safe";
}

const VERDICT_CONFIG = {
  danger: {
    label: "위험 — AI 생성 가능성 높음",
    badge: "🔴",
    emoji: "⚠️",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-600",
    bar: "bg-red-400",
  },
  warning: {
    label: "주의 — AI 생성 가능성 있음",
    badge: "🟡",
    emoji: "🔍",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-600",
    bar: "bg-yellow-400",
  },
  safe: {
    label: "안전 — 실제 영상일 가능성 높음",
    badge: "🟢",
    emoji: "✅",
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-600",
    bar: "bg-green-400",
  },
};

export default function ResultPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();

  const [result, setResult] = useState(null);
  const [taskStatus, setTaskStatus] = useState("pending");
  const [message, setMessage] = useState("분석 결과를 불러오는 중입니다.");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!taskId) {
      setError("잘못된 접근입니다. task_id가 없습니다.");
      return;
    }

    let intervalId = null;
    let stopped = false;

    const fetchResult = async () => {
      try {
        const res = await analyzeService.getResult(taskId);

        if (stopped) return;

        setTaskStatus(res.status);

        if (res.status === "pending") {
          setMessage(res.message || "작업 대기 중입니다.");
          return;
        }

        if (res.status === "processing") {
          setMessage(res.message || "AI 분석이 진행 중입니다.");
          return;
        }

        if (res.status === "completed") {
          setResult(res.result);
          setMessage("분석이 완료되었습니다.");
          if (intervalId) clearInterval(intervalId);
          return;
        }

        if (res.status === "failed") {
          setError(res.message || "분석에 실패했습니다.");
          if (intervalId) clearInterval(intervalId);
          return;
        }

        setMessage(res.message || "상태를 확인하는 중입니다.");
      } catch (err) {
        setError(err.response?.data?.message || "결과를 불러오지 못했습니다.");
        if (intervalId) clearInterval(intervalId);
      }
    };

    fetchResult();
    intervalId = setInterval(fetchResult, 2000);

    return () => {
      stopped = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [taskId]);

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <ErrorMessage message={error} />
        <button
          onClick={() => navigate("/")}
          className="w-full mt-4 py-3 border-2 border-gray-200 text-gray-600 text-sm font-bold rounded-xl hover:border-gray-300 hover:text-gray-800 transition-colors"
        >
          ← 홈으로 돌아가기
        </button>
      </main>
    );
  }

  if (!result) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center">
          <p className="text-2xl mb-3">🔎 영상 분석 중</p>
          <p className="text-sm text-gray-500 mb-6">{message}</p>
          <p className="text-xs text-gray-400 mb-4">현재 상태: {taskStatus}</p>
          <Loading />
        </div>
      </main>
    );
  }

  const probability = Math.round((result.confidence || 0) * 100);
  const verdict = getVerdict(result.confidence || 0);
  const cfg = VERDICT_CONFIG[verdict];
  const details = result.analysis_details || {};
  const regions = details.detected_regions || [];

  return (
    <main className="max-w-2xl mx-auto px-6 py-10">
      <div className={`flex items-center gap-4 p-5 rounded-2xl border-2 ${cfg.bg} ${cfg.border} mb-5`}>
        <span className="text-4xl">{cfg.emoji}</span>
        <div>
          <p className={`text-lg font-bold ${cfg.text}`}>{cfg.badge} {cfg.label}</p>
          <p className="text-sm text-gray-500 mt-0.5">AI가 분석한 결과입니다. 참고 자료로만 활용하세요.</p>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-4">
        <div className="flex justify-between text-sm font-bold mb-2">
          <span className="text-gray-700">AI 생성 확률</span>
          <span className={cfg.text}>{probability}%</span>
        </div>
        <div className="h-3 bg-gray-100 rounded-full overflow-hidden mb-1">
          <div
            className={`h-full rounded-full transition-all duration-700 ${cfg.bar}`}
            style={{ width: `${probability}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>🟢 안전 (낮음)</span>
          <span>🔴 위험 (높음)</span>
        </div>
      </div>

      {details.details && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-4">
          <p className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-2">분석 내용</p>
          <p className="text-sm text-gray-700 leading-relaxed">{details.details}</p>
        </div>
      )}

      {regions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-4">
          <p className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-3">감지된 이상 영역</p>
          <div className="flex flex-col gap-3">
            {regions.map((r, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                <div className="w-7 h-7 rounded-full bg-red-500 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {i + 1}
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-800">{r.issue}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    위치: x={r.x}, y={r.y} / 크기: {r.width}×{r.height}px
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <p className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-2">결과 공유</p>
          <p className="text-xs text-gray-500 mb-3 leading-relaxed">
            허위정보 확산을 막기 위해 주변에 알려주세요.
          </p>
          <button
            onClick={() => navigator.clipboard.writeText(window.location.href)}
            className="w-full py-2 bg-blue-500 text-white text-sm font-bold rounded-xl hover:bg-blue-600 transition-colors mb-2"
          >
            🔗 링크 복사
          </button>
          <button className="w-full py-2 bg-yellow-400 text-gray-900 text-sm font-bold rounded-xl hover:bg-yellow-500 transition-colors">
            💬 카카오톡 공유
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <p className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-2">결과가 틀렸나요?</p>
          <p className="text-xs text-gray-500 mb-3 leading-relaxed">
            알려주시면 AI 학습에 반영됩니다.
          </p>
          <button className="w-full py-2 bg-green-50 border border-green-200 text-green-700 text-sm font-bold rounded-xl hover:bg-green-100 transition-colors mb-2">
            ✅ 실제 영상입니다
          </button>
          <button className="w-full py-2 bg-red-50 border border-red-200 text-red-600 text-sm font-bold rounded-xl hover:bg-red-100 transition-colors">
            ❌ 확실히 가짜예요
          </button>
        </div>
      </div>

      <button
        onClick={() => navigate("/")}
        className="w-full py-3 border-2 border-gray-200 text-gray-600 text-sm font-bold rounded-xl hover:border-gray-300 hover:text-gray-800 transition-colors"
      >
        ← 다른 영상 분석하기
      </button>
    </main>
  );
}