// src/components/result/AnalysisChart.jsx
import { useState } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { getScoreColor } from "../../constants/verdict";

const MODULE_META = {
  clip:      { label: "얼굴 조작",   desc: "AI 생성 시각 패턴 탐지 (CLIP DeCoF)" },
  frequency: { label: "배경 생성",   desc: "픽셀 노이즈·FFT 압축 흔적 분석" },
  metadata:  { label: "음성·메타",   desc: "인코더·해상도·C2PA 마커 검사" },
  temporal:  { label: "움직임 패턴", desc: "프레임 간 광류·텍스처 일관성" },
  rppg:      { label: "얼굴 혈류",   desc: "얼굴 혈류 신호 분석" },
  fft_deep:  { label: "주파수 심화", desc: "주파수 심화 분석" },
  physics:   { label: "물리 일관성", desc: "물리 일관성 분석" },
  audio:     { label: "음성",        desc: "음성 합성 탐지" },
};

function normalizeFromDetails(details) {
  if (!Array.isArray(details) || !details.length) return [];
  return details
    .map(d => ({
      key:    d.module,
      label:  MODULE_META[d.module]?.label ?? d.module_name ?? d.module,
      desc:   MODULE_META[d.module]?.desc  ?? d.description ?? "",
      score:  Math.round((d.score ?? 0) * 100),
      reason: d.reason ?? d.description ?? "",
    }));
}

function normalizeFromModuleScores(moduleScores) {
  if (!moduleScores || typeof moduleScores !== "object") return [];
  return Object.entries(moduleScores).map(([key, score]) => ({
    key,
    label:  MODULE_META[key]?.label ?? key,
    desc:   MODULE_META[key]?.desc  ?? "",
    score:  Math.round((score ?? 0) * 100),
    reason: "",
  }));
}

function buildFallbackScores(confidence) {
  const base = confidence ?? 0.5;
  return [
    { key: "clip",      label: "얼굴 조작",   desc: "", score: Math.round(Math.min(1, base * 1.1) * 100),                score: Math.round(Math.min(1, base * 1.1) * 100), reason: "백엔드 연동 후 표시" },
    { key: "frequency", label: "배경 생성",   desc: "", score: Math.round(Math.min(1, base * 0.9) * 100),                reason: "백엔드 연동 후 표시" },
    { key: "metadata",  label: "음성·메타",   desc: "", score: Math.round(Math.min(1, base * 0.6) * 100),                reason: "백엔드 연동 후 표시" },
    { key: "temporal",  label: "움직임 패턴", desc: "", score: Math.round(Math.min(1, base * (0.7 + base * 0.4)) * 100), reason: "백엔드 연동 후 표시" },
  ];
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background:   "var(--surface)",
      border:       "1px solid var(--border)",
      borderRadius: "var(--r-md)",
      padding:      "8px 12px",
      fontSize:     12,
      maxWidth:     200,
    }}>
      <p style={{ fontWeight: 700, color: "var(--text-1)", marginBottom: 2 }}>{d.label}</p>
      <p style={{ color: "var(--brand)", fontWeight: 600 }}>{d.score}%</p>
      {d.desc && <p style={{ color: "var(--text-3)", lineHeight: 1.4, marginTop: 2 }}>{d.desc}</p>}
    </div>
  );
}

function TableRow({ row, isLast }) {
  const color = getScoreColor(row.score / 100);
  return (
    <tr style={{ borderBottom: isLast ? "none" : "1px solid var(--border)" }}>
      <td style={{ padding: "10px 12px", width: 90, color: "var(--text-2)", fontSize: 13, fontWeight: 500, whiteSpace: "nowrap" }}>
        {row.label}
      </td>
      <td style={{ padding: "10px 12px", width: 140 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ flex: 1, height: 6, borderRadius: 99, background: "var(--border)", overflow: "hidden" }}>
            <div style={{ width: `${row.score}%`, height: "100%", background: color.fill, borderRadius: 99, transition: "width 0.6s ease" }} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, color: color.text, minWidth: 32, textAlign: "right" }}>
            {row.score}%
          </span>
        </div>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <span style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.5 }}>
          {row.reason || row.desc || "—"}
        </span>
      </td>
    </tr>
  );
}

export default function AnalysisChart({ moduleScores, confidence, detailsStr, details }) {
  const [view, setView] = useState("chart");

  const rows = (() => {
    const fromDetails = normalizeFromDetails(details);
    if (fromDetails.length) return fromDetails;

    const fromScores = normalizeFromModuleScores(moduleScores);
    if (fromScores.length) return fromScores;

    return buildFallbackScores(confidence);
  })();

  if (!rows.length) return null;

  const radarData = rows.map(r => ({ ...r, fullMark: 100 }));
  const avgScore  = rows.reduce((s, r) => s + r.score, 0) / rows.length;
  const radarFill = avgScore >= 70 ? "#E24B4A" : avgScore >= 40 ? "#EF9F27" : "#22c55e";

  return (
    <div className="card mb-fluid-sm">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <span className="sec-label" style={{ marginBottom: 2 }}>분석 모듈 점수</span>
          <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>AI 탐지 모듈별 위험도</p>
        </div>
        <div style={{ display: "flex", gap: 4, background: "var(--border)", borderRadius: "var(--r-md)", padding: 3 }}>
          {[["chart", "차트"], ["table", "표"]].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              style={{
                padding:      "4px 12px",
                borderRadius: "var(--r-sm, 6px)",
                border:       "none",
                cursor:       "pointer",
                fontSize:     12,
                fontWeight:   view === key ? 600 : 400,
                background:   view === key ? "var(--surface)" : "transparent",
                color:        view === key ? "var(--text-1)"  : "var(--text-3)",
                transition:   "all 0.2s",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "chart" && (
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--text-2)", fontWeight: 500 }} />
              <Tooltip content={<ChartTooltip />} />
              <Radar
                name="위험도"
                dataKey="score"
                stroke={radarFill}
                fill={radarFill}
                fillOpacity={0.25}
                strokeWidth={2}
                dot={{ r: 4, fill: radarFill, strokeWidth: 0 }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      {view === "table" && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["모듈", "위험도", "근거"].map(h => (
                <th key={h} style={{
                  textAlign: "left", fontSize: 11, fontWeight: 600,
                  padding: "6px 12px", background: "var(--brand-light)", color: "var(--text-2)",
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <TableRow key={row.key} row={row} isLast={i === rows.length - 1} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}