// src/components/result/AnalysisChart.jsx
//
// 분석 모듈별 점수를 레이더 차트 + 상세 표로 시각화합니다.
//
// ── 백엔드 연동 현황 ──────────────────────────────────────────────
// [현재] 백엔드가 module_scores를 계산하지만 반환 JSON에 포함하지 않음.
//        postprocess.py의 build_result_json()에 module_scores를 추가하면
//        이 컴포넌트가 자동으로 실제 데이터를 표시합니다.
//
//        백엔드 수정 위치:
//          backend_api/ai_engine/src/postprocess.py
//          build_result_json() 반환 dict에 아래 추가:
//            "module_scores": module_scores,   ← 이미 계산된 변수
//            "risk_level":    risk,
//            "reliability":   reliability,
//
// [임시] module_scores가 없을 때 confidence 기반 임시 데이터를 사용합니다.
//        실제 데이터가 오면 임시 데이터는 자동으로 무시됩니다.
//
// ── targets 연동 현황 ─────────────────────────────────────────────
// [현재] 사용자가 선택한 targets(face·bg·motion·voice)가 백엔드
//        run_ai_video_analysis()에 전달되지 않아 실제 분석에 반영 안 됨.
//        백엔드는 항상 clip·frequency·metadata·temporal 4개를 전부 실행.
//
// [연동 후] worker.py의 start_ai_analysis()에서 targets를
//           run_ai_video_analysis(video_path, output_dir, targets)로 전달하고,
//           inference.py에서 ANALYZERS를 targets 기반으로 필터링하면
//           선택한 모듈만 실행됩니다. 그때 이 차트도 선택 모듈만 표시됩니다.
// ─────────────────────────────────────────────────────────────────

import { useState } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { getScoreColor } from "../../constants/verdict";

// ── 모듈 메타데이터 ──────────────────────────────────────────────
// [현재] 백엔드 module_scores key(clip·frequency·metadata·temporal)를
//        사용자가 선택한 타겟 이름(얼굴 조작 등)으로 임시 매핑해서 표시.
//
// [TODO] 백엔드 targets 연동 완료 후 아래 작업 필요:
//        1. label을 백엔드 모듈 실제 이름으로 변경
//           (예: clip → "CLIP 분석", frequency → "주파수 분석" 등)
//        2. targets.js id와 MODULE_META key를 통일
const MODULE_META = {
  // 백엔드 모듈명  →  사용자 타겟 이름 (임시 매핑)
  clip:      { label: "얼굴 조작",   desc: "AI 생성 시각 패턴 탐지 (CLIP DeCoF)" },
  frequency: { label: "배경 생성",   desc: "픽셀 노이즈·FFT 압축 흔적 분석" },
  metadata:  { label: "음성·메타",   desc: "인코더·해상도·C2PA 마커 검사" },
  temporal:  { label: "움직임 패턴", desc: "프레임 간 광류·텍스처 일관성" },
};

// ── details_str 파싱 ─────────────────────────────────────────────
// 백엔드 analysis_details.details 문자열에서 모듈별 근거를 추출합니다.
// 형식: "판별 메시지. 근거: CLIP(...): ... / FFT: ... / ..."
//
// [TODO] 백엔드 postprocess.py의 build_result_json()에 아래를 추가하면
//        이 파싱 없이 module_scores를 직접 사용합니다:
//          "module_scores": module_scores,
//          "risk_level":    risk,
//          "reliability":   reliability,
function parseDetailsStr(detailsStr) {
  if (!detailsStr) return {};

  // "근거: " 이후 부분만 추출
  const reasonPart = detailsStr.split("근거:")[1];
  if (!reasonPart) return {};

  // " / "로 분리해서 모듈별 근거 배열
  const parts = reasonPart.split(" / ").map(s => s.trim()).filter(Boolean);

  // 각 근거를 모듈 key에 매핑
  // 백엔드 reason 형식: "CLIP(DeCoF...): ...", "FFT: ...", "메타데이터 이상 없음", "시공간: ..."
  const map = {};
  for (const part of parts) {
    if (part.startsWith("CLIP"))       map.clip      = part;
    else if (part.startsWith("FFT"))   map.frequency = part;
    else if (part.includes("메타데이터")) map.metadata  = part;
    else if (part.startsWith("시공간")) map.temporal  = part;
  }
  return map;
}

// ── 임시 데이터 생성 ─────────────────────────────────────────────
// [TODO] 백엔드에서 module_scores가 내려오면 이 함수는 호출되지 않음.
//        postprocess.py에 module_scores 추가 후 제거 가능.
function buildFallbackScores(confidence, detailsStr) {
  const base     = confidence ?? 0.5;
  const reasonMap = parseDetailsStr(detailsStr); // 실제 근거 문자열 파싱

  return {
    clip:      { score: Math.min(1, base * 1.1),               status: "ok", reason: reasonMap.clip      || "백엔드 연동 후 표시" },
    frequency: { score: Math.min(1, base * 0.9),               status: "ok", reason: reasonMap.frequency || "백엔드 연동 후 표시" },
    metadata:  { score: Math.min(1, base * 0.6),               status: "ok", reason: reasonMap.metadata  || "백엔드 연동 후 표시" },
    temporal:  { score: Math.min(1, base * (0.7 + base * 0.4)),status: "ok", reason: reasonMap.temporal  || "백엔드 연동 후 표시" },
  };
}

// ── module_scores → 차트/표 데이터 변환 ─────────────────────────
function normalizeScores(moduleScores) {
  return Object.entries(moduleScores)
    .filter(([, v]) => v.status === "ok")
    .map(([key, v]) => ({
      key,
      label:  MODULE_META[key]?.label ?? key,
      desc:   MODULE_META[key]?.desc  ?? "",
      score:  Math.round((v.score ?? 0) * 100),
      reason: v.reason ?? "",
    }));
}

// ── 커스텀 툴팁 ─────────────────────────────────────────────────
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

// ── 상세 표 행 ───────────────────────────────────────────────────
function TableRow({ row, isLast }) {
  const color = getScoreColor(row.score / 100);
  return (
    <tr style={{ borderBottom: isLast ? "none" : "1px solid var(--border)" }}>
      {/* 모듈명 */}
      <td style={{ padding: "10px 12px", width: 90, color: "var(--text-2)", fontSize: 13, fontWeight: 500, whiteSpace: "nowrap" }}>
        {row.label}
      </td>
      {/* 점수 바 */}
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
      {/* 근거 */}
      <td style={{ padding: "10px 12px" }}>
        <span style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.5 }}>
          {row.reason || row.desc}
        </span>
      </td>
    </tr>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────────────
export default function AnalysisChart({ moduleScores, confidence, detailsStr }) {
  const [view, setView] = useState("chart"); // "chart" | "table"

  // module_scores가 없으면 details 문자열을 파싱해서 실제 근거 표시
  // [TODO] 백엔드 postprocess.py에 module_scores 추가 후 fallback 분기 제거 가능
  const raw    = moduleScores ?? buildFallbackScores(confidence, detailsStr);
  const rows   = normalizeScores(raw);
  const isTemp = !moduleScores; // 임시 데이터 여부 표시용

  if (!rows.length) return null;

  // recharts용 데이터 (레이더 차트)
  const radarData = rows.map(r => ({ ...r, fullMark: 100 }));

  // 레이더 채우기 색상 — 평균 점수 기반
  const avgScore = rows.reduce((s, r) => s + r.score, 0) / rows.length;
  const radarFill = avgScore >= 70 ? "#E24B4A" : avgScore >= 40 ? "#EF9F27" : "#22c55e";

  return (
    <div className="card mb-fluid-sm">

      {/* 헤더 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <span className="sec-label" style={{ marginBottom: 2 }}>분석 모듈 점수</span>
          {/* [TODO] 백엔드 targets 연동 후 아래 문구를 "선택한 모듈 결과"로 변경 */}
          <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
            {isTemp
              ? "* 상세 점수 준비 중 — 참고용 데이터입니다"  // 임시 데이터일 때
              : "AI 탐지 모듈별 위험도"                       // 실제 데이터일 때
            }
          </p>
        </div>
        {/* 뷰 전환 토글 */}
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

      {/* 차트 뷰 */}
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

      {/* 표 뷰 */}
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