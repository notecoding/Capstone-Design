// src/components/result/AnalysisTimeline.jsx
import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

function resolveImgUrl(frame, taskId) {
  if (frame.path)      return `${API_URL}/${frame.path}`;
  if (frame.file_name) return `${API_URL}/storage/results/${taskId}/${frame.file_name}`;
  return null;
}

function FramePlaceholder() {
  return (
    <div className="w-full flex flex-col items-center justify-center gap-fluid-xs"
         style={{ height: 160, background: "var(--brand-light)" }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="var(--brand)"
           strokeWidth={1.5} style={{ width: 36, height: 36, opacity: 0.5 }}>
        <rect x="2" y="3" width="20" height="18" rx="3"/>
        <path d="M10 8l6 4-6 4V8z" fill="currentColor" stroke="none"/>
      </svg>
      <span className="text-fluid-xs" style={{ color: "var(--text-3)" }}>
        프레임 이미지를 불러올 수 없어요
      </span>
    </div>
  );
}

function FrameImage({ src }) {
  const [failed, setFailed] = useState(false);
  if (failed || !src) return <FramePlaceholder />;
  return (
    <img src={src} alt="의심 프레임"
         className="w-full object-cover"
         style={{ maxHeight: 220, display: "block" }}
         onError={() => setFailed(true)} />
  );
}

export default function AnalysisTimeline({ frames, duration, taskId }) {
  const [selected, setSelected] = useState(null);
  const [tooltip,  setTooltip]  = useState(null);
  const total = duration || 60;

  return (
    <div className="card mb-fluid-sm">
      <span className="sec-label">분석 타임라인 — 의심 구간 클릭</span>

      <div className="relative mb-1" style={{ height: 24 }}>
        <div className="absolute" style={{
          top: "50%", left: 0, right: 0, transform: "translateY(-50%)",
          height: 8, background: "var(--brand-light)",
          border: "1px solid var(--border)", borderRadius: 99,
        }} />
        {frames.map((f, i) => {
          const pct  = (f.timestamp / total) * 100;
          const prob = Math.round((f.probability || 0) * 100);
          return (
            <div key={i} className="absolute z-10"
                 style={{ top: "50%", left: `${pct}%`, transform: "translate(-50%,-50%)", cursor: "pointer" }}
                 onMouseEnter={() => setTooltip(i)}
                 onMouseLeave={() => setTooltip(null)}
                 onClick={() => setSelected(p => p === i ? null : i)}>
              {tooltip === i && (
                <div className="absolute whitespace-nowrap z-20 text-fluid-xs px-2 py-1 rounded"
                     style={{ bottom: 20, left: "50%", transform: "translateX(-50%)",
                              background: "var(--text-1)", color: "#fff" }}>
                  {fmtTime(f.timestamp)} · {prob}% 의심
                </div>
              )}
              <div style={{
                width: 14, height: 14, borderRadius: "50%",
                border: "2px solid var(--surface)",
                background: f.probability >= 0.7 ? "#E24B4A" : "#EF9F27",
                transform: selected === i ? "scale(1.5)" : "scale(1)",
                transition: "transform 0.15s",
              }} />
            </div>
          );
        })}
      </div>

      <div className="flex justify-between text-fluid-xs mb-fluid-md" style={{ color: "var(--text-3)" }}>
        {[0, 0.25, 0.5, 0.75, 1].map(r => <span key={r}>{fmtTime(total * r)}</span>)}
      </div>

      {selected !== null && frames[selected] && (
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r-md)", overflow: "hidden" }}>
          <FrameImage src={resolveImgUrl(frames[selected], taskId)} />
          <div className="p-fluid-sm" style={{ background: "var(--surface)" }}>
            <div className="flex items-center justify-between mb-fluid-xs">
              <span className="text-fluid-sm font-bold" style={{ color: "var(--text-1)" }}>
                {fmtTime(frames[selected].timestamp)}
              </span>
              <span className="text-fluid-xs font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: "#FCEBEB", color: "#A32D2D" }}>
                {Math.round((frames[selected].probability || 0) * 100)}% 의심
              </span>
            </div>
            {frames[selected].tags?.length > 0 && (
              <div className="flex flex-wrap gap-fluid-xs">
                {frames[selected].tags.map((tag, ti) => (
                  <span key={ti} className="text-fluid-xs px-2 py-0.5 rounded"
                        style={{ background: "#FEF3E2", color: "#92400E" }}>
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}