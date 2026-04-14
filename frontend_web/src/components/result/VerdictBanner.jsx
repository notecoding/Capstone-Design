// src/components/result/VerdictBanner.jsx
export default function VerdictBanner({ cfg }) {
  return (
    <div className="flex items-center gap-fluid-md p-fluid-md mb-fluid-sm"
         style={{ background: cfg.bg, border: `1.5px solid ${cfg.border}`, borderRadius: "var(--r-lg)" }}>
      <div className="flex items-center justify-center flex-shrink-0"
           style={{ width: 44, height: 44, borderRadius: 12, background: cfg.bar }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
             stroke="#fff" strokeWidth="2.5" strokeLinecap="round">
          <path d="M12 9v4M12 17h.01"/>
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        </svg>
      </div>
      <div>
        <p className="text-fluid-md font-bold" style={{ color: cfg.text }}>{cfg.label}</p>
        <p className="text-fluid-xs mt-1" style={{ color: cfg.text, opacity: 0.7 }}>
          AI가 분석한 결과입니다. 참고 자료로만 활용하세요.
        </p>
      </div>
    </div>
  );
}