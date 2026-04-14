import { useState }        from "react";
import { useNavigate }     from "react-router-dom";
import { analyzeService }  from "../api/analyzeService";
import { VideoUpload }     from "../components/upload";
import { AnalysisHistory } from "../components/history";

const STATS = [
  { value: "98.2%", label: "탐지 정확도" },
  { value: "12초",  label: "평균 분석 시간" },
  { value: "4종",   label: "탐지 모델" },
];

const HOW_TO = [
  { step: "01", title: "영상 업로드",  desc: "파일을 끌어다 놓거나\nYouTube 링크를 붙여넣으세요" },
  { step: "02", title: "AI 자동 분석", desc: "얼굴·배경·음성을\n자동으로 검사합니다" },
  { step: "03", title: "결과 확인",    desc: "AI 생성 확률과\n의심 구간을 알려드립니다" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  async function handleSubmit(payload) {
    setError("");
    try {
      const result = payload.type === "file"
        ? await analyzeService.uploadFile(payload.value)
        // TODO: 백엔드 targets 연동 완료 후 아래 주석 해제
        // ? await analyzeService.uploadFile(payload.value, payload.targets)
        : await analyzeService.analyzeUrl(payload.value);
        // TODO: await analyzeService.analyzeUrl(payload.value, payload.targets);
      navigate(`/result/${result.task_id}`, {
        state: { name: payload.type === "file" ? payload.value.name : payload.value, targets: payload.targets },
      });
    } catch (err) {
      setError(err.response?.data?.detail || "업로드 중 오류가 발생했습니다.");
    }
  }

  return (
    <main className="max-w-content mx-auto px-fluid-md">

      {/* 히어로 */}
      <section className="text-center pt-fluid-xl pb-fluid-lg">
       
        <h1 className="mt-fluid-lg text-fluid-2xl font-bold leading-tight mb-fluid-sm"
            style={{ color: "var(--text-1)", letterSpacing: "-0.5px" }}>
          이 영상,{" "}
          <em className="not-italic" style={{ color: "var(--brand)" }}>진짜</em>일까요?
        </h1>

        <p className="text-fluid-base leading-relaxed mb-fluid-lg" style={{ color: "var(--text-2)" }}>
          딥페이크·AI 생성 영상을 몇 초 만에 탐지합니다.<br />
          파일을 올리거나 유튜브 링크를 붙여넣으세요.
        </p>

        <div className="inline-flex overflow-hidden"
             style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)" }}>
          {STATS.map(({ value, label }, i) => (
            <div key={label} className="text-center py-fluid-sm px-fluid-md"
                 style={{ borderRight: i < 2 ? "1px solid var(--border)" : "none" }}>
              <p className="text-fluid-lg font-bold" style={{ color: "var(--brand)" }}>{value}</p>
              <p className="text-fluid-xs mt-1"       style={{ color: "var(--text-3)" }}>{label}</p>
            </div>
          ))}
        </div>
      </section>

      <VideoUpload onSubmit={handleSubmit} />

      {error && (
        <p className="text-fluid-sm text-center mt-fluid-sm" style={{ color: "var(--brand)" }}>
          ⚠️ {error}
        </p>
      )}

      {/* 사용 방법 */}
      <section className="mt-fluid-xl mb-fluid-xl">
        <span className="sec-label" style={{ textAlign: "center", display: "block" }}>사용 방법</span>
        <div className="grid grid-cols-3 gap-fluid-md">
          {HOW_TO.map(({ step, title, desc }) => (
            <div key={step} className="card flex flex-col items-center text-center">
              <span className="text-fluid-xs font-bold mb-fluid-sm"
                    style={{ color: "var(--brand)", letterSpacing: "0.12em" }}>{step}</span>
              <p className="text-fluid-md font-bold mb-fluid-xs" style={{ color: "var(--text-1)" }}>{title}</p>
              <p className="text-fluid-sm leading-relaxed whitespace-pre-line" style={{ color: "var(--text-3)" }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <AnalysisHistory />
    </main>
  );
}