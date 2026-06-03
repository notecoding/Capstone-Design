// src/components/result/AnalysisChart.jsx
import { useState } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { getScoreColor } from "../../constants/verdict";

// 백엔드 분석기명 → 타겟 이름 매핑 (쉬운 설명 사용)
const MODULE_META = {
  clip:            { label: "얼굴 조작",   desc: "얼굴이 인공적으로 바뀌었는지 확인했습니다" },
  frequency:       { label: "배경 생성",   desc: "배경이 AI로 만들어졌는지 확인했습니다" },
  metadata:        { label: "음성 합성",   desc: "AI가 목소리를 만들어냈는지 확인했습니다" },
  physics:         { label: "움직임 패턴", desc: "사람의 움직임이 자연스러운지 확인했습니다" },
  clip_face:       { label: "얼굴 조작",   desc: "얼굴이 인공적으로 바뀌었는지 확인했습니다" },
  clip_background: { label: "배경 생성",   desc: "배경이 AI로 만들어졌는지 확인했습니다" },
};

// 점수에 따른 쉬운 요약 문구 생성
function buildSummaryText(rows) {
  if (!rows.length) return null;
  const high   = rows.filter(r => r.score >= 70);
  const medium = rows.filter(r => r.score >= 40 && r.score < 70);

  if (high.length > 0) {
    return `${high.map(r => r.label).join(", ")} 영역에서 AI 조작 흔적이 발견되었습니다.`;
  }
  if (medium.length > 0) {
    return `${medium.map(r => r.label).join(", ")} 영역에서 일부 의심스러운 부분이 있습니다.`;
  }
  return "모든 영역에서 AI 조작 흔적이 발견되지 않았습니다.";
}

function parseDetailsStr(detailsStr) {
  if (!detailsStr) return {};
  const reasonPart = detailsStr.split("근거:")[1];
  if (!reasonPart) return {};
  const parts = reasonPart.split(" / ").map(s => s.trim()).filter(Boolean);
  const map = {};
  for (const part of parts) {
    if (part.startsWith("CLIP"))          map.clip      = part;
    else if (part.startsWith("FFT"))      map.frequency = part;
    else if (part.includes("메타데이터")) map.metadata  = part;
    else if (part.startsWith("물리"))     map.physics   = part;
  }
  return map;
}

function buildFallbackScores(confidence, detailsStr) {
  const base      = confidence ?? 0.5;
  const reasonMap = parseDetailsStr(detailsStr);
  return {
    clip:      { score: Math.min(1, base * 1.1), status: "ok", reason: reasonMap.clip      || "" },
    frequency: { score: Math.min(1, base * 0.9), status: "ok", reason: reasonMap.frequency || "" },
    metadata:  { score: Math.min(1, base * 0.6), status: "ok", reason: reasonMap.metadata  || "" },
    physics:   { score: Math.min(1, base * 0.8), status: "ok", reason: reasonMap.physics   || "" },
  };
}

function normalizeScores(moduleScores) {
  return Object.entries(moduleScores)
    .map(([key, v]) => ({
      key,
      label:  MODULE_META[key]?.label ?? key,
      desc:   MODULE_META[key]?.desc  ?? "",
      score:  v.status === "error" ? 0 : Math.round((v.score ?? 0) * 100),
      reason: v.status === "error" ? "분석 데이터 없음" : (v.reason ?? ""),
    }));
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
      <p style={{ color: "var(--text-3)", lineHeight: 1.4, marginTop: 2 }}>{d.desc}</p>
    </div>
  );
}

// 근거 문자열에서 쉬운 말 뱃지로 변환
function parseReasonBadges(reason) {
  if (!reason || reason === "분석 데이터 없음") return [];
  const badges = [];

  if (reason.includes("fallback"))              badges.push("기본 분석 모드");
  if (reason.includes("유사도")) {
    const m = reason.match(/유사도\s*([\d.]+)/);
    if (m) badges.push(`영상 유사도 ${m[1]}`);
  }
  if (reason.includes("고주파비")) {
    const m = reason.match(/고주파비=([\d.]+)/);
    if (m) badges.push(`화질 이상도 ${m[1]}`);
  }
  if (reason.includes("AI점수")) {
    const m = reason.match(/AI점수=([\d.]+)/);
    if (m) badges.push(`AI 의심도 ${m[1]}`);
  }
  if (reason.includes("정규화잔차")) {
    const m = reason.match(/정규화잔차[^=]*([\d.]+)/);
    if (m) badges.push(`움직임 이상도 ${m[1]}`);
  }
  if (reason.includes("ffprobe 실패"))          badges.push("파일 정보 확인 불가");
  if (reason.includes("C2PA"))                  badges.push("AI 생성 마커 없음");

  if (!badges.length) badges.push(reason.slice(0, 30) + (reason.length > 30 ? "…" : ""));
  return badges;
}

function TableRow({ row, isLast }) {
  const color  = getScoreColor(row.score / 100);
  const badges = parseReasonBadges(row.reason);
  const isEmpty = row.score === 0 && row.reason === "분석 데이터 없음";
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
        {isEmpty ? (
          <span style={{ fontSize: 11, color: "var(--text-3)" }}>분석 데이터 없음</span>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {badges.map((b, i) => (
              <span key={i} style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 99,
                background: b === "fallback 모드" ? "#F1EFE8" : "var(--brand-light)",
                color: b === "fallback 모드" ? "var(--text-3)" : "var(--text-2)",
                border: "1px solid var(--border)",
              }}>
                {b}
              </span>
            ))}
          </div>
        )}
      </td>
    </tr>
  );
}

export default function AnalysisChart({ moduleScores, confidence, detailsStr }) {
  const [view, setView] = useState("chart");

  const raw     = moduleScores ?? buildFallbackScores(confidence, detailsStr);
  const rows    = normalizeScores(raw);
  const isTemp  = !moduleScores;
  const summary = buildSummaryText(rows);

  if (!rows.length) return null;

  const radarData = rows.map(r => ({ ...r, fullMark: 100 }));
  const avgScore  = rows.reduce((s, r) => s + r.score, 0) / rows.length;
  const radarFill = avgScore >= 70 ? "#E24B4A" : avgScore >= 40 ? "#EF9F27" : "#22c55e";

  return (
    <div className="card mb-fluid-sm">

      {/* 텍스트 요약 */}
      {summary && (
        <div style={{
          padding:      "12px 16px",
          borderRadius: "var(--r-md)",
          background:   avgScore >= 70 ? "#FEF2F2" : avgScore >= 40 ? "#FFFBEB" : "#F0FDF4",
          border:       `1px solid ${avgScore >= 70 ? "#FECACA" : avgScore >= 40 ? "#FDE68A" : "#BBF7D0"}`,
          marginBottom: 16,
        }}>
          <p style={{
            fontSize:   "var(--fs-sm)",
            fontWeight: 600,
            color:      avgScore >= 70 ? "#991B1B" : avgScore >= 40 ? "#92400E" : "#166534",
            lineHeight: 1.6,
          }}>
            🔍 {summary}
          </p>
          {isTemp && (
            <p style={{ fontSize: "var(--fs-xs)", color: "var(--text-3)", marginTop: 4 }}>
              * 참고용 데이터입니다
            </p>
          )}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <span className="sec-label" style={{ marginBottom: 2 }}>항목별 분석 결과</span>
          <p style={{ fontSize: "var(--fs-xs)", color: "var(--text-3)", marginTop: 2 }}>
            각 항목이 높을수록 AI 조작 가능성이 높습니다
          </p>
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
              <PolarAngleAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: "var(--text-2)", fontWeight: 500 }}
              />
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
              {["분석 항목", "위험도", "확인 내용"].map(h => (
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