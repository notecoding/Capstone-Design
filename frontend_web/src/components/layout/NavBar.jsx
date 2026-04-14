// src/components/layout/NavBar.jsx
import { Link, useLocation } from "react-router-dom";

export default function NavBar() {
  const { pathname } = useLocation();
  const onResult = pathname.startsWith("/result");

  return (
    <nav className="w-full px-fluid-md flex items-center justify-between"
         style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", height: 64 }}>

      <Link to="/" className="flex items-center gap-fluid-sm">
        <div className="flex items-center justify-center flex-shrink-0"
             style={{ width: 34, height: 34, background: "var(--brand)", borderRadius: 10 }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2l1.8 3.6 4 .6-2.9 2.8.7 4L8 11l-3.6 1.9.7-4L2.2 6.2l4-.6z" fill="#fff"/>
          </svg>
        </div>
        <span className="text-fluid-lg font-bold"
              style={{ color: "var(--text-1)", letterSpacing: "-0.3px" }}>
          TrueView
        </span>
      </Link>

      <div className="flex gap-fluid-sm">
        <Link to="/" className="text-fluid-sm font-bold px-4 py-2 rounded-fluid-sm"
              style={{
                background: onResult ? "transparent" : "var(--brand)",
                color:      onResult ? "var(--text-2)" : "#fff",
                border:     onResult ? "1px solid var(--border)" : "none",
              }}>
          분석하기
        </Link>
      </div>
    </nav>
  );
}