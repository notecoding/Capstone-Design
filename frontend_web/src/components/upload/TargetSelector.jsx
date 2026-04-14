// src/components/upload/TargetSelector.jsx
import { TARGET_LIST } from "../../constants/targets";

export default function TargetSelector({ targets, onToggle }) {
  return (
    <div>
      <span className="sec-label">분석 타겟 선택</span>
      <div className="grid grid-cols-2 gap-fluid-sm">
        {TARGET_LIST.map(({ id, label, sub }) => (
          <div key={id} onClick={() => onToggle(id)}
               className="flex items-center gap-fluid-sm p-fluid-sm cursor-pointer transition-all"
               style={{
                 border:       targets[id] ? "1.5px solid var(--brand)"  : "1.5px solid var(--border)",
                 background:   targets[id] ? "var(--brand-light)"        : "var(--surface)",
                 borderRadius: "var(--r-md)",
               }}>
            <div className="flex items-center justify-center flex-shrink-0"
                 style={{
                   width: 20, height: 20, borderRadius: 6,
                   background: targets[id] ? "var(--brand)" : "transparent",
                   border:     targets[id] ? "none"         : "1.5px solid var(--border)",
                 }}>
              {targets[id] && (
                <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
                  <path d="M1 4.5l3 3L10 1" stroke="#fff" strokeWidth="1.8"
                        strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-fluid-sm font-semibold" style={{ color: "var(--text-1)" }}>{label}</p>
              <p className="text-fluid-xs mt-0.5"        style={{ color: "var(--text-3)" }}>{sub}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}