// src/pages/HomePage.jsx
// 영상 업로드 → analyzeService 호출 → task_id 받아서 결과 페이지로 이동

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeService } from "../api/services";  // axios 직접 대신 서비스 사용
import VideoUpload from "../components/VideoUpload";

export default function HomePage() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);  // 업로드 진행 여부
  const [progress, setProgress]   = useState(0);      // 업로드 진행률 0~100
  const [error, setError]         = useState("");

  // ── 분석 시작 핸들러 ──────────────────────────────────────────
  // payload: { type: 'file' | 'url', value: File | string }
  async function handleSubmit(payload) {
    setError("");
    setUploading(true);
    setProgress(0);

    try {
      let result;

      if (payload.type === "file") {
        // 파일 업로드 — 진행률 콜백 전달
        result = await analyzeService.uploadFile(payload.value, setProgress);
      } else {
        // URL 분석
        result = await analyzeService.analyzeUrl(payload.value);
      }

      // 분석 결과 페이지로 이동
      navigate(`/result/${result.task_id}`);

    } catch (err) {
      const msg = err.response?.data?.detail || "업로드 중 오류가 발생했습니다.";
      setError(msg);
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }

  return (
    <main className="max-w-4xl mx-auto px-6">

      {/* ── 히어로 텍스트 ── */}
      <h1 className="text-center text-4xl font-bold mb-6 mt-16">
        <p className="text-5xl mb-3">가짜 뉴스 시대</p>
        <p>당신의 눈을 지키는 디지털 돋보기</p>
      </h1>
      <p className="text-lg text-gray-500 mb-12 text-center leading-relaxed">
        "이 영상, 진짜일까?" 고민하지 마세요.<br />
        AI가 분석하고 TrueView가 알려드립니다.
      </p>

      {/* ── 업로드 컴포넌트 ── */}
      <VideoUpload
        onSubmit={handleSubmit}
        uploading={uploading}
        uploadProgress={progress}
      />

      {/* ── 에러 메시지 ── */}
      {error && (
        <p className="text-sm text-red-500 text-center mt-4">⚠️ {error}</p>
      )}
    </main>
  );
}