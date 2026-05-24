// src/components/result/AnalysisTable.jsx
import { getScoreColor } from "../../constants/verdict";

const MODULE_LABEL = {
  clip:      "CLIP 분석",
  frequency: "주파수 분석",
  metadata:  "메타데이터",
  temporal:  "시공간 분석",
  face:      "얼굴 조작",
  bg:        "배경 생성",
  motion:    "움직임 패턴",
  voice:     "음성 합성",
};

function EmptyFallback({ details }) {
  if (!details) return null;
  return (
    <div className="card mb-fluid-sm">
      <span className="sec-label">분석 상세</span>
      <p className="text-fluid-sm" style={{ color: "var(--text-2)", lineHeight: 1.7 }}>
        {details}
      </p>
      <p className="text-fluid-xs mt-fluid-xs" style={{ color: "var(--text-3)" }}>
        * 상세 모듈 점수는 현재 버전에서 제공되지 않습니다.
      </p>
    </div>
  );
}

function normalizeModuleScores(moduleScores) {
  return Object.entries(moduleScores)
    .filter(([, v]) => v.status === "ok")
    .map(([key, v]) => ({
      key,
      label:  MODULE_LABEL[key] ?? key,
      score:  v.score ?? 0,
      reason: v.reason ?? "",
      tags:   v.reason ? [v.reason] : [],
    }));
}

export default function AnalysisTable({ scores, moduleScores, details }) {
  const rows = (() => {
    if (Array.isArray(scores) && scores.length > 0) return scores;
    if (moduleScores && typeof moduleScores === "object" && Object.keys(moduleScores).length > 0)
      return normalizeModuleScores(moduleScores);
    return [];
  })();

  if (!rows.length) return <EmptyFallback details={details} />;

  return (
    <div className="card mb-fluid-sm">
      <span className="sec-label">분석 상세</span>
      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["항목", "위험도", "근거"].map(h => (
              <th key={h} className="text-left text-fluid-xs font-semibold px-fluid-sm py-fluid-xs"
                  style={{ background: "var(--brand-light)", color: "var(--text-2)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const pct   = Math.round((row.score ?? 0) * 100);
            const color = getScoreColor(row.score ?? 0);
            const tags  = row.tags?.length ? row.tags : (row.reason ? [row.reason] : []);
            return (
              <tr key={row.key ?? i}
                  style={{ borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : "none" }}>
                <td className="text-fluid-sm px-fluid-sm py-fluid-sm whitespace-nowrap"
                    style={{ color: "var(--text-2)", width: 110 }}>{row.label}</td>
                <td className="px-fluid-sm py-fluid-sm" style={{ width: 140 }}>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 rounded-full overflow-hidden" style={{ height: 6, background: "var(--border)" }}>
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color.fill }} />
                    </div>
                    <span className="text-fluid-xs font-semibold"
                          style={{ color: color.text, minWidth: 32, textAlign: "right" }}>
                      {pct}%
                    </span>
                  </div>
                </td>
                <td className="px-fluid-sm py-fluid-sm">
                  {tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {tags.map((tag, ti) => (
                        <span key={ti} className="text-fluid-xs px-2 py-0.5 rounded"
                              style={{
                                background: (row.score ?? 0) >= 0.4 ? "#FEF3E2" : "var(--brand-light)",
                                color:      (row.score ?? 0) >= 0.4 ? "#92400E" : "var(--text-2)",
                              }}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-fluid-xs" style={{ color: "var(--text-3)" }}>—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}