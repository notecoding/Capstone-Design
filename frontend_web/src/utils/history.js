// src/utils/history.js
const STORAGE_KEY = "trueview_history";
const MAX_ITEMS   = 10;

// ── localStorage 헬퍼 ────────────────────────────────────────────
// 쿠키(4KB 한계)에서 localStorage(5MB)로 변경.
// 만료 기능은 없으므로 사용자가 직접 지우거나 clearHistory() 호출 시 삭제됨.

function getStorage(key) {
  try { return JSON.parse(localStorage.getItem(key)); }
  catch { return null; }
}

function setStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); }
  catch (e) { console.error("히스토리 저장 실패:", e); }
}

function removeStorage(key) {
  localStorage.removeItem(key);
}

// ── 공개 API ─────────────────────────────────────────────────────

export function loadHistory() {
  return getStorage(STORAGE_KEY) ?? [];
}

export function addHistory({ taskId, name, apiResult }) {
  if (apiResult?.status !== "success") return;

  const confidence  = apiResult.confidence ?? 0;
  const probability = Math.round(confidence * 100);
  const verdict     = probability >= 70 ? "danger" : probability >= 40 ? "warning" : "safe";

  const newItem = {
    id:          taskId,
    name:        name || "알 수 없음",
    probability,
    verdict,
    isAi:        apiResult.is_ai,
    date:        new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" }),
    result:      apiResult,  // 결과 전체 저장 (재조회용 — localStorage라 용량 여유 있음)
  };

  const prev    = loadHistory();
  const updated = [newItem, ...prev].slice(0, MAX_ITEMS);
  setStorage(STORAGE_KEY, updated);
}

export function clearHistory() {
  removeStorage(STORAGE_KEY);
}