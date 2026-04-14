// src/components/history/HistoryItem.jsx
import { useNavigate }    from "react-router-dom";
import { VERDICT_CONFIG } from "../../constants/verdict";

function shortenName(name = "", maxLen = 42) {
  if (name.length <= maxLen) return name;
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  return name.slice(0, maxLen - ext.length - 3) + "..." + ext;
}

export default function HistoryItem({ item }) {
  const navigate = useNavigate();
  const cfg      = VERDICT_CONFIG[item.verdict] ?? VERDICT_CONFIG.safe;

  function handleClick() {
    navigate(`/result/${item.id}`, {
      state: {
        name:        item.name,
        fromHistory: true,
        result:      item.result,  // 저장된 결과 전달 → 폴링 없이 바로 표시
      },
    });
  }

  return (
    <div onClick={handleClick}
         className="flex items-center gap-fluid-sm p-fluid-sm cursor-pointer transition-all"
         style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-md)" }}
         onMouseEnter={e => e.currentTarget.style.borderColor = "var(--text-3)"}
         onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border)"}>

      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: cfg.dot }} />

      <div className="flex-1 min-w-0">
        <p className="text-fluid-sm font-semibold truncate" style={{ color: "var(--text-1)" }}>
          {shortenName(item.name)}
        </p>
        <p className="text-fluid-xs mt-0.5" style={{ color: "var(--text-3)" }}>{item.date}</p>
      </div>

      <div className="flex items-center gap-fluid-xs flex-shrink-0">
        <div className="rounded-full overflow-hidden" style={{ width: 64, height: 5, background: "var(--border)" }}>
          <div className="h-full rounded-full" style={{ width: `${item.probability}%`, background: cfg.dot }} />
        </div>
        <span className="text-fluid-xs font-bold w-8 text-right" style={{ color: "var(--text-2)" }}>
          {item.probability}%
        </span>
      </div>

      <span className="text-fluid-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
            style={{ background: cfg.histBadge.bg, color: cfg.histBadge.color }}>
        {cfg.histLabel}
      </span>
    </div>
  );
}