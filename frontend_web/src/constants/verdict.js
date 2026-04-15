// src/constants/verdict.js
export const VERDICT_CONFIG = {
  danger: {
    label: "위험 — AI 생성 가능성 높음",
    bg: "#FCEBEB", border: "#F09595", text: "#A32D2D", bar: "#E24B4A",
    dot: "#E24B4A", histLabel: "AI 의심",
    histBadge: { bg: "#FCEBEB", color: "#A32D2D" },
  },
  warning: {
    label: "주의 — AI 생성 가능성 있음",
    bg: "#FAEEDA", border: "#FAC775", text: "#854F0B", bar: "#EF9F27",
    dot: "#EF9F27", histLabel: "주의",
    histBadge: { bg: "#FAEEDA", color: "#854F0B" },
  },
  safe: {
    label: "안전 — 실제 영상일 가능성 높음",
    bg: "#DCFCE7", border: "#86EFAC", text: "#166534", bar: "#22c55e",
    dot: "#22c55e", histLabel: "정상",
    histBadge: { bg: "#DCFCE7", color: "#166534" },
  },
};

export function getVerdict(confidence = 0) {
  if (confidence >= 0.7) return "danger";
  if (confidence >= 0.4) return "warning";
  return "safe";
}

export function getScoreColor(score = 0) {
  if (score >= 0.7) return { text: "#A32D2D", fill: "#E24B4A" };
  if (score >= 0.4) return { text: "#854F0B", fill: "#EF9F27" };
  return               { text: "#166534", fill: "#22c55e" };
}

export const ANALYSIS_STEPS = [
  { key: "pending",    label: "대기 중",    icon: "⏳" },
  { key: "processing", label: "AI 분석 중", icon: "🔎" },
  { key: "completed",  label: "분석 완료",  icon: "✅" },
];