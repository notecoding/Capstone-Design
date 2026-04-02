import { useState, useRef } from "react";

// 허용 확장자 & 최대 용량
const ALLOWED_EXT = [".mp4", ".avi", ".mov"];
const MAX_MB = 500;

// YouTube / 카카오 링크 패턴
const URL_PATTERN = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be|kakao\.com|kakaotv\.com).+/i;

// 파일 유효성 검사 → 에러 문자열, 없으면 null
function validateFile(file) {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXT.includes(ext)) return "MP4, AVI, MOV 파일만 가능합니다";
  if (file.size > MAX_MB * 1024 * 1024) return `파일이 너무 큽니다 (최대 ${MAX_MB}MB)`;
  return null;
}

/* 업로드 화살표 아이콘 (SVG) — 인라인 속성으로 크기·색상 고정 */
function UploadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#3b82f6"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={28}
      height={28}
    >
      {/* 위쪽 화살표 */}
      <path d="M12 15V3" />
      <path d="M7 8l5-5 5 5" />
      {/* 아래쪽 받침선 */}
      <path d="M20 21H4" />
    </svg>
  );
}

/* ─────────────────────────────────────────
 * VideoUpload
 * Props:
 *   onSubmit({ type: 'url'|'file', value }) – 분석 시작 시 호출
 * ───────────────────────────────────────── */
export default function VideoUpload({ onSubmit }) {
  const [url, setUrl]           = useState("");
  const [file, setFile]         = useState(null);   // 선택된 File 객체
  const [dragging, setDragging] = useState(false);  // 드래그 오버 여부
  const [error, setError]       = useState("");
  const [progress, setProgress] = useState(null);   // 0~100 or null

  const inputRef = useRef(null);

  // ── 파일 선택 (드롭 · input 공용) ──
  function pickFile(f) {
    if (!f) return;
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError("");
    setFile(f);
  }

  // ── 제출 ──
  function handleSubmit() {
    setError("");

    if (url.trim()) {
      if (!URL_PATTERN.test(url.trim())) { setError("YouTube 또는 카카오 링크를 입력해 주세요"); return; }
      onSubmit?.({ type: "url", value: url.trim() });
      return;
    }

    if (!file) { setError("파일을 선택하거나 링크를 입력해 주세요"); return; }

    // 모의 진행률 — 실제 구현 시 Axios onUploadProgress 로 교체
    let pct = 0;
    setProgress(0);
    const t = setInterval(() => {
      pct += Math.floor(Math.random() * 15) + 5;
      if (pct >= 100) {
        clearInterval(t);
        setProgress(null);
        onSubmit?.({ type: "file", value: file });
      } else {
        setProgress(pct);
      }
    }, 150);
  }

  return (
    <div className="font-sans max-w-5xl mx-auto bg-white border-2 border-dashed border-gray-300 rounded-2xl p-20 pb-6 hover:bg-blue-50 transition-colors">

      {/* ── 드롭존 상단 영역 (아이콘 + 텍스트) ── */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); }}
        onDrop={e => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]); }}
        className={`flex flex-col items-center text-center cursor-pointer rounded-xl transition-colors duration-200 py-4
          ${dragging ? "bg-blue-50" : "bg-transparent"}`}
      >
        {/* 업로드 화살표 아이콘 — 파일 선택 시 체크 이모지로 전환 */}
        <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mb-3">
          {file ? <span className="text-2xl">✅</span> : <UploadIcon />}
        </div>

        {/* 안내 텍스트 */}
        <p className="text-base font-bold text-gray-800 mb-1">
          {file ? file.name : "영상 파일을 여기에 끌어다 놓으세요"}
        </p>
        <p className="text-sm text-gray-400">
          {file
            ? `${(file.size / 1024 / 1024).toFixed(1)} MB · 다시 선택하려면 클릭하세요`
            : "또는 아래에 유튜브 · 카카오톡 링크를 붙여넣으세요"}
        </p>
      </div>

      {/* 숨겨진 file input */}
      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.avi,.mov"
        onChange={e => pickFile(e.target.files[0])}
        className="hidden"
      />

      {/* ── URL 입력 행 ── */}
      <div className="flex items-center gap-2 my-4 bg-gray-800 rounded-xl px-4 py-3">
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://youtube.com/watch?v=..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-gray-300 placeholder-gray-500 min-w-0 font-sans"
        />
        {/* 분석 시작 버튼 */}
        <button
          onClick={handleSubmit}
          disabled={progress !== null}
          className={`flex-shrink-0 px-4 py-1.5 rounded-lg text-sm font-bold text-white transition-colors
            ${progress !== null ? "bg-gray-600 cursor-not-allowed" : "bg-blue-500 hover:bg-blue-600 cursor-pointer"}`}
        >
          {progress !== null ? `${progress}%` : "분석 시작"}
        </button>
      </div>

      {/* ── 진행률 바 (파일 업로드 중) ── */}
      {progress !== null && (
        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden mb-3">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* ── 지원 포맷 뱃지 ── */}
      <div className="flex gap-2 flex-wrap">
        {["MP4", "AVI", "MOV", "YouTube 링크", "카카오톡 링크"].map(label => (
          <span
            key={label}
            className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-full px-3 py-1"
          >
            {label}
          </span>
        ))}
      </div>

      {/* 에러 메시지 */}
      {error && (
        <p className="text-sm text-red-500 mt-3 mb-0">
          ⚠️ {error}
        </p>
      )}
    </div>
  );
}