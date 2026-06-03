// src/components/result/AnalyzingScreen.jsx
import { useState, useEffect } from "react";

// ── 분석 작업 목록 ───────────────────────────────────────────────
// 백엔드 실행 순서: 프레임 추출 → clip → frequency → metadata → (motion 선택 시 physics 추가)
// 사용자에게는 타겟 선택 이름으로 표시.
// face·background·voice 타겟은 region 탐지만 수행하고 고유 분석기는 미구현 상태.
//
// ※ ALL_TASKS는 프레임 추출(extract) 1개 + 분석 모듈 4개 = 총 5개 항목
const ALL_TASKS = [
  { id: "extract", key: null,     name: "프레임 추출",      sub: "영상에서 핵심 프레임 선별" },
  { id: "face",    key: "face",   name: "얼굴 조작 탐지",   sub: "딥페이크 패턴 분석" },
  { id: "bg",      key: "bg",     name: "배경 생성 분석",   sub: "AI 생성 패턴 검사" },
  { id: "motion",  key: "motion", name: "움직임 패턴",      sub: "부자연스러운 모션 탐지" },
  { id: "voice",   key: "voice",  name: "음성·메타데이터",  sub: "합성 음성 및 파일 정보 분석" },
];

const STEP_DELAY_MS = 600;

function filterTasks(targets) {
  // 백엔드가 항상 기본 분석기(clip·frequency·metadata) 전체를 실행하므로 targets 무관하게 전체 표시.
  // 추후 타겟별 고유 분석기가 추가되면 아래 주석을 해제하고 위 return을 제거.
  return ALL_TASKS;
  // return ALL_TASKS.filter(t => t.key === null || targets.includes(t.key));
}

function getTaskStatus(idx, taskStatus, completedCount) {
  if (taskStatus === "completing" || taskStatus === "completed") {
    if (idx < completedCount) return "done";
    if (idx === completedCount) return "active";
    return "wait";
  }
  const doneCount = taskStatus === "pending" ? 0 : 1;
  if (idx < doneCount)   return "done";
  if (idx === doneCount) return "active";
  return "wait";
}

function SpinnerIcon() {
  return (
    <div style={{
      width: 10, height: 10,
      border: "1.5px solid var(--brand)",
      borderTopColor: "transparent",
      borderRadius: "50%",
      animation: "tv-spin 1s linear infinite",
    }} />
  );
}

function CheckIcon({ color = "#166534" }) {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"
         stroke={color} strokeWidth="2" strokeLinecap="round">
      <path d="M1.5 5l2.5 2.5 4.5-4.5"/>
    </svg>
  );
}

export default function AnalyzingScreen({ taskStatus = "pending", message, targets }) {
  const tasks    = filterTasks(targets);
  const stepIdx  = taskStatus === "pending" ? 0 : 1;
  const [pct, setPct]               = useState(0);
  const [completedCount, setCount]  = useState(0);

  useEffect(() => {
    if (taskStatus === "completing") {
      const target = 100;
      const total  = tasks.length * STEP_DELAY_MS;
      const step   = (target - pct) / (total / 80);
      const id = setInterval(() => {
        setPct(prev => {
          if (prev >= target) { clearInterval(id); return target; }
          return Math.min(prev + step, target);
        });
      }, 80);
      return () => clearInterval(id);
    }
    if (taskStatus !== "processing") return;
    const id = setInterval(() => {
      setPct(prev => {
        if (prev >= 85) { clearInterval(id); return prev; }
        return Math.min(prev + Math.random() * 2 + 0.3, 85);
      });
    }, 120);
    return () => clearInterval(id);
  }, [taskStatus]);

  useEffect(() => {
    if (taskStatus !== "completing") return;
    setCount(0);
    const timers = tasks.map((_, i) =>
      setTimeout(() => setCount(i + 1), (i + 1) * STEP_DELAY_MS)
    );
    return () => timers.forEach(clearTimeout);
  }, [taskStatus]);

  const displayPct   = Math.round(pct);
  const isCompleting = taskStatus === "completing";

  return (
    <>
      <style>{`
        @keyframes tv-spin  { to { transform: rotate(360deg); } }
        @keyframes tv-pulse { 0%,100% { opacity:1; } 50% { opacity:.35; } }
      `}</style>

      <div className="card text-center" style={{ padding: "var(--sp-xl) var(--sp-lg)" }}>

        <div className="mx-auto mb-fluid-md flex items-center justify-center"
             style={{ width: 72, height: 72, borderRadius: 20,
                      background: "var(--brand-light)", border: "1.5px solid var(--border)" }}>
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="12" stroke="var(--border)" strokeWidth="3"/>
            <circle cx="16" cy="16" r="12" stroke="var(--brand)" strokeWidth="3"
                    strokeDasharray="50 26" fill="none"
                    style={{ transformOrigin: "center",
                             animation: "tv-spin 1.2s linear infinite" }}/>
          </svg>
        </div>

        <p className="text-fluid-lg font-bold mb-fluid-xs"
           style={{ color: "var(--text-1)", letterSpacing: "-0.3px" }}>
          {isCompleting ? "분석 완료 중..." : "영상 분석 중입니다"}
        </p>
        <p className="text-fluid-sm mb-fluid-lg" style={{ color: "var(--text-3)", lineHeight: 1.6 }}>
          {isCompleting
            ? "결과를 정리하고 있어요. 잠시만 기다려 주세요."
            : (message || "AI가 영상을 꼼꼼히 살펴보고 있어요. 잠시만 기다려 주세요.")}
        </p>

        <div className="flex items-center justify-center mb-fluid-lg">
          {["업로드", "분석 중", "결과 생성"].map((label, i) => {
            const isDone   = isCompleting ? i <= 1 : i < stepIdx;
            const isActive = isCompleting ? i === 2 : i === stepIdx;
            return (
              <div key={label} className="flex items-center">
                {i > 0 && (
                  <div style={{
                    width: 48, height: 2,
                    background: (isDone || isActive) ? "var(--brand)" : "var(--border)",
                    transition: "background 0.4s",
                  }} />
                )}
                <div className="flex flex-col items-center" style={{ gap: 6 }}>
                  <div className="flex items-center justify-center"
                       style={{
                         width: 36, height: 36, borderRadius: "50%",
                         background: isDone    ? "#DCFCE7"
                                   : isActive  ? "var(--brand-light)"
                                   :             "#F1EFE8",
                         border: isActive ? "2px solid var(--brand)" : "none",
                         transition: "all 0.4s",
                         animation: isActive ? "tv-pulse 1.6s ease-in-out infinite" : "none",
                       }}>
                    {isDone ? (
                      <CheckIcon color="#166534" />
                    ) : (
                      <span style={{ fontSize: 11, fontWeight: 700,
                                     color: isActive ? "var(--brand)" : "var(--text-3)" }}>
                        {String(i + 1).padStart(2, "0")}
                      </span>
                    )}
                  </div>
                  <span style={{
                    fontSize: "var(--fs-xs)",
                    fontWeight: isActive ? 700 : 400,
                    color: isActive ? "var(--brand)"
                         : isDone   ? "#166534"
                         :            "var(--text-3)",
                    whiteSpace: "nowrap",
                  }}>
                    {label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mb-fluid-lg" style={{ textAlign: "left" }}>
          <div className="flex justify-between items-baseline mb-fluid-xs">
            <span className="text-fluid-xs font-semibold"
                  style={{ color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em" }}>
              AI 분석 진행률
            </span>
            <span style={{ fontSize: "clamp(18px,1.8vw,24px)", fontWeight: 800, color: "var(--brand)" }}>
              {displayPct}%
            </span>
          </div>
          <div className="rounded-full overflow-hidden" style={{ height: 8, background: "#F1EFE8" }}>
            <div className="h-full rounded-full"
                 style={{ width: `${displayPct}%`, background: "var(--brand)", transition: "width 0.4s ease" }} />
          </div>
        </div>

        <div className="flex flex-col gap-fluid-xs" style={{ textAlign: "left" }}>
          {tasks.map((task, idx) => {
            const ts = getTaskStatus(idx, taskStatus, completedCount);
            return (
              <div key={task.id}
                   className="flex items-center gap-fluid-sm"
                   style={{
                     padding: "10px 14px",
                     borderRadius: "var(--r-md)",
                     border: ts === "active" ? "1px solid var(--brand)" : "1px solid var(--border)",
                     background: ts === "active" ? "var(--brand-light)"
                               : ts === "done"   ? "#FAFAF8"
                               :                   "var(--surface)",
                     transition: "all 0.35s ease",
                   }}>
                <div className="flex items-center justify-center flex-shrink-0"
                     style={{
                       width: 20, height: 20, borderRadius: "50%",
                       background: ts === "done"   ? "#DCFCE7"
                                 : ts === "active" ? "var(--brand-light)"
                                 :                   "#F1EFE8",
                       border: ts === "active" ? "1.5px solid var(--brand)" : "none",
                       transition: "all 0.35s ease",
                     }}>
                  {ts === "done"   && <CheckIcon />}
                  {ts === "active" && <SpinnerIcon />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-fluid-sm font-semibold"
                     style={{ color: ts === "wait" ? "var(--text-3)" : "var(--text-1)" }}>
                    {task.name}
                  </p>
                  <p className="text-fluid-xs mt-0.5" style={{ color: "var(--text-3)" }}>
                    {ts === "active" ? task.sub + "..." : task.sub}
                  </p>
                </div>
                <span className="text-fluid-xs font-semibold flex-shrink-0"
                      style={{
                        color: ts === "done"   ? "#166534"
                             : ts === "active" ? "var(--brand)"
                             :                   "var(--border)",
                        transition: "color 0.35s ease",
                      }}>
                  {ts === "done" ? "완료" : ts === "active" ? "진행 중" : "대기"}
                </span>
              </div>
            );
          })}
        </div>

      </div>
    </>
  );
}