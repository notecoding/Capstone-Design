// src/utils/history.js
const COOKIE_KEY = "trueview_history";
const MAX_ITEMS  = 10;
const EXPIRES    = 30;

function getCookie(key) {
  const match = document.cookie.split("; ").find(r => r.startsWith(`${key}=`));
  if (!match) return null;
  try { return JSON.parse(decodeURIComponent(match.split("=")[1])); }
  catch { return null; }
}

function setCookie(key, value, days) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${key}=${encodeURIComponent(JSON.stringify(value))}; expires=${expires}; path=/; SameSite=Lax`;
}

function removeCookie(key) {
  document.cookie = `${key}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/`;
}

export function loadHistory() {
  return getCookie(COOKIE_KEY) ?? [];
}

export function addHistory({ taskId, name, apiResult }) {
  if (apiResult?.status !== "success") return;

  const confidence  = apiResult.confidence ?? 0;
  const probability = Math.round(confidence * 100);
  const verdict     = probability >= 70 ? "danger" : probability >= 40 ? "warn" : "safe";

  const newItem = {
    id:          taskId,
    name:        name || "알 수 없음",
    probability,
    verdict,
    isAi:        apiResult.is_ai,
    date:        new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" }),
    result:      apiResult,   // ← 결과 전체 저장 (기록 재조회용)
  };

  const prev    = loadHistory();
  const updated = [newItem, ...prev].slice(0, MAX_ITEMS);
  setCookie(COOKIE_KEY, updated, EXPIRES);
}

export function clearHistory() {
  removeCookie(COOKIE_KEY);
}