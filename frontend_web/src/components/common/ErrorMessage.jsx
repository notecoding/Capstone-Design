// src/components/common/ErrorMessage.jsx
export default function ErrorMessage({ message = "오류가 발생했습니다." }) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 rounded-fluid-md text-fluid-sm"
         style={{ background: "#FEF3E2", border: "1px solid #FDE8C2", color: "#92400E" }}>
      <span>⚠️</span>
      <span>{message}</span>
    </div>
  );
}