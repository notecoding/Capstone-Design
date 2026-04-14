// src/components/result/ShareCard.jsx
export default function ShareCard() {
  return (
    <div className="grid grid-cols-2 gap-fluid-sm mb-fluid-sm">
      <div className="card">
        <span className="sec-label">결과 공유</span>
        <p className="text-fluid-xs mb-fluid-sm" style={{ color: "var(--text-2)", lineHeight: 1.6 }}>
          허위정보 확산을 막기 위해 주변에 알려주세요.
        </p>
        <button className="btn-sm mb-fluid-xs"
                style={{ background: "var(--brand)", color: "#fff" }}
                onClick={() => navigator.clipboard.writeText(window.location.href)}>
          🔗 링크 복사
        </button>
        <button className="btn-sm" style={{ background: "#FEF3C7", color: "#92400E" }}>
          💬 카카오톡 공유
        </button>
      </div>
      <div className="card">
        <span className="sec-label">결과가 틀렸나요?</span>
        <p className="text-fluid-xs mb-fluid-sm" style={{ color: "var(--text-2)", lineHeight: 1.6 }}>
          알려주시면 AI 학습에 반영됩니다.
        </p>
        <button className="btn-sm mb-fluid-xs"
                style={{ background: "#DCFCE7", color: "#166534", border: "1px solid #86EFAC" }}>
          ✅ 실제 영상입니다
        </button>
        <button className="btn-sm"
                style={{ background: "#FCEBEB", color: "#A32D2D", border: "1px solid #F09595" }}>
          ❌ 확실히 가짜예요
        </button>
      </div>
    </div>
  );
}