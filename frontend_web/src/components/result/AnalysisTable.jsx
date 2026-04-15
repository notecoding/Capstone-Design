// src/components/result/AnalysisTable.jsx
import { getScoreColor } from "../../constants/verdict";

export default function AnalysisTable({ scores = [] }) {
  if (!scores.length) return null;
  return (
    <div className="card mb-fluid-sm">
      <span className="sec-label">분석 상세</span>
      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["항목", "위험도", "감지 내용"].map(h => (
              <th key={h} className="text-left text-fluid-xs font-semibold px-fluid-sm py-fluid-xs"
                  style={{ background: "var(--brand-light)", color: "var(--text-2)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {scores.map((row, i) => {
            const pct   = Math.round(row.score * 100);
            const color = getScoreColor(row.score);
            return (
              <tr key={row.key}
                  style={{ borderBottom: i < scores.length - 1 ? "1px solid var(--border)" : "none" }}>
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
                  <div className="flex flex-wrap gap-1">
                    {row.tags?.map((tag, ti) => (
                      <span key={ti} className="text-fluid-xs px-2 py-0.5 rounded"
                            style={{
                              background: row.score >= 0.4 ? "#FEF3E2" : "var(--brand-light)",
                              color:      row.score >= 0.4 ? "#92400E" : "var(--text-2)",
                            }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}