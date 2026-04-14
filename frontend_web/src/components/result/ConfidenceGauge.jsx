// src/components/result/ConfidenceGauge.jsx
export default function ConfidenceGauge({ probability, cfg }) {
  return (
    <div className="card mb-fluid-sm">
      <div className="flex justify-between items-baseline mb-fluid-xs">
        <span className="text-fluid-base" style={{ color: "var(--text-2)" }}>AI 생성 확률</span>
        <span className="font-bold" style={{ fontSize: "clamp(28px,2.5vw,38px)", color: cfg.bar }}>
          {probability}%
        </span>
      </div>
      <div className="rounded-full overflow-hidden mb-1" style={{ height: 10, background: "var(--border)" }}>
        <div className="h-full rounded-full transition-all duration-700"
             style={{ width: `${probability}%`, background: cfg.bar }} />
      </div>
      <div className="flex justify-between text-fluid-xs" style={{ color: "var(--text-3)" }}>
        <span>안전 (낮음)</span><span>위험 (높음)</span>
      </div>
    </div>
  );
}