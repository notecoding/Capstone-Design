// src/components/upload/DropZone.jsx
import { useRef } from "react";

export default function DropZone({ file, dragging, onFilePick, onDragChange }) {
  const inputRef = useRef(null);

  return (
    <>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); onDragChange(true); }}
        onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) onDragChange(false); }}
        onDrop={e => { e.preventDefault(); onDragChange(false); onFilePick(e.dataTransfer.files[0]); }}
        className="flex flex-col items-center text-center cursor-pointer rounded-fluid-md py-fluid-md transition-colors"
        style={{ background: dragging ? "var(--brand-light)" : "transparent" }}
      >
        <div className="flex items-center justify-center mb-fluid-sm"
             style={{ width: 56, height: 56, background: "var(--brand-light)", borderRadius: 14 }}>
          {file ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                 stroke="var(--brand)" strokeWidth="2.5" strokeLinecap="round">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                 stroke="var(--brand)" strokeWidth="2" strokeLinecap="round">
              <path d="M12 15V3"/><path d="M7 8l5-5 5 5"/><path d="M20 21H4"/>
            </svg>
          )}
        </div>
        <p className="text-fluid-md font-bold mb-fluid-xs" style={{ color: "var(--text-1)" }}>
          {file ? file.name : "영상을 여기에 끌어다 놓으세요"}
        </p>
        <p className="text-fluid-sm" style={{ color: "var(--text-3)" }}>
          {file
            ? `${(file.size / 1024 / 1024).toFixed(1)} MB · 다시 선택하려면 클릭`
            : "클릭해서 파일 선택 또는 아래 링크 입력"}
        </p>
      </div>
      <input ref={inputRef} type="file" accept=".mp4,.avi,.mov"
             onChange={e => onFilePick(e.target.files[0])} className="hidden" />
    </>
  );
}