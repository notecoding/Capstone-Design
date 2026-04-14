// src/components/layout/Footer.jsx
export default function Footer() {
  return (
    <footer className="w-full px-fluid-md py-fluid-md text-center text-fluid-xs"
            style={{ borderTop: "1px solid var(--border)", color: "var(--text-3)", background: "var(--surface)" }}>
      © {new Date().getFullYear()} TrueView — AI 영상 판별 서비스
    </footer>
  );
}