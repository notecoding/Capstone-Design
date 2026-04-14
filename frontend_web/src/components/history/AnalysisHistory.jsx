// src/components/history/AnalysisHistory.jsx
import useAnalysisHistory from "../../hooks/useAnalysisHistory";
import HistoryItem        from "./HistoryItem";

export default function AnalysisHistory() {
  const { history, handleClear } = useAnalysisHistory();

  return (
    <section className="mt-fluid-xl mb-fluid-xl">
      <div className="flex items-center justify-between mb-fluid-md">
        <h2 className="text-fluid-md font-bold" style={{ color: "var(--text-1)" }}>
          최근 분석 기록
        </h2>
        {history.length > 0 && (
          <button onClick={handleClear} className="text-fluid-xs px-3 py-1 rounded-fluid-sm"
                  style={{ color: "var(--text-3)", border: "1px solid var(--border)",
                           background: "transparent", cursor: "pointer" }}>
            기록 지우기
          </button>
        )}
      </div>

      {history.length === 0 ? (
        <div className="text-center py-fluid-xl rounded-fluid-lg"
             style={{ background: "var(--brand-light)", border: "1px solid var(--border)" }}>
          <p className="text-fluid-base" style={{ color: "var(--text-2)" }}>아직 분석 기록이 없어요</p>
          <p className="text-fluid-xs mt-fluid-xs" style={{ color: "var(--text-3)" }}>
            영상을 업로드하면 여기에 기록됩니다
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-fluid-xs">
          {history.map(item => <HistoryItem key={item.id} item={item} />)}
        </div>
      )}
    </section>
  );
}