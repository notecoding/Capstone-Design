import { useState } from "react";
import { DEFAULT_TARGETS, ALLOWED_EXT, MAX_FILE_MB, URL_PATTERN } from "../../constants/targets";
import DropZone       from "./DropZone";
import TargetSelector from "./TargetSelector";

function validateFile(file) {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXT.includes(ext))           return "MP4, AVI, MOV 파일만 가능합니다";
  if (file.size > MAX_FILE_MB * 1024 * 1024) return `파일이 너무 큽니다 (최대 ${MAX_FILE_MB}MB)`;
  return null;
}

export default function VideoUpload({ onSubmit }) {
  const [url,      setUrl]      = useState("");
  const [file,     setFile]     = useState(null);
  const [dragging, setDragging] = useState(false);
  const [error,    setError]    = useState("");
  const [progress, setProgress] = useState(null);
  const [targets,  setTargets]  = useState(DEFAULT_TARGETS);

  const isLoading = progress !== null;

  function pickFile(f) {
    if (!f) return;
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError(""); setFile(f);
  }

  function handleSubmit() {
    setError("");
    const selected = Object.entries(targets).filter(([, v]) => v).map(([k]) => k);
    if (!selected.length) { setError("분석 타겟을 1개 이상 선택해 주세요"); return; }

    if (url.trim()) {
      if (!URL_PATTERN.test(url.trim())) { setError("YouTube 링크를 입력해 주세요"); return; }
      onSubmit?.({ type: "url", value: url.trim(), targets: selected });
      return;
    }
    if (!file) { setError("파일을 선택하거나 링크를 입력해 주세요"); return; }

    let pct = 0;
    setProgress(0);
    const t = setInterval(() => {
      pct += Math.floor(Math.random() * 15) + 5;
      if (pct >= 100) { clearInterval(t); setProgress(null); onSubmit?.({ type: "file", value: file, targets: selected }); }
      else setProgress(pct);
    }, 150);
  }

  return (
    <div className="mt-fluid-md max-w-content mx-auto"
         style={{ background: "var(--surface)", border: "2px dashed var(--border)", borderRadius: "var(--r-xl)", padding: "var(--sp-lg)" }}>

      <DropZone file={file} dragging={dragging} onFilePick={pickFile} onDragChange={setDragging} />

      {/* URL 입력 */}
      <div className="flex items-center gap-fluid-sm my-fluid-sm px-fluid-sm py-fluid-sm"
           style={{ background: "var(--text-1)", borderRadius: "var(--r-md)" }}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2" style={{ flexShrink: 0 }}>
          <circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 010 20"/>
        </svg>
        <input value={url} onChange={e => setUrl(e.target.value)}
               onKeyDown={e => e.key === "Enter" && handleSubmit()}
               placeholder="https://youtube.com/watch?v=..."
               className="flex-1 bg-transparent border-none outline-none text-fluid-sm min-w-0"
               style={{ color: "#aaa", fontFamily: "inherit" }} />
      </div>

      {/* 진행률 */}
      {isLoading && (
        <div className="mt-fluid-sm rounded-full overflow-hidden mb-fluid-sm" style={{ height: 6, background: "var(--border)" }}>
          <div className="h-full rounded-full transition-all duration-200"
               style={{ width: `${progress}%`, background: "var(--brand)" }} />
        </div>
      )}

      {/* 포맷 뱃지 */}
      <div className="flex gap-fluid-xs flex-wrap mt-fluid-sm mb-fluid-sm">
        {["MP4", "AVI", "MOV", "YouTube"].map(l => (
          <span key={l} className="text-fluid-xs px-3 py-1 rounded-full"
                style={{ background: "var(--brand-light)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
            {l}
          </span>
        ))}
      </div>

      <hr className="divider" />

      <TargetSelector targets={targets} onToggle={id => setTargets(p => ({ ...p, [id]: !p[id] }))} />

      {error && <p className="text-fluid-sm mt-fluid-sm" style={{ color: "var(--brand)" }}>⚠️ {error}</p>}

      <button className="btn-brand mt-fluid-md" onClick={handleSubmit} disabled={isLoading}>
        {isLoading ? `분석 준비 중... ${progress}%` : "분석 시작하기"}
      </button>
    </div>
  );
}