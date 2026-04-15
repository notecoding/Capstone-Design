// src/api/analyzeService.js
import api from "./axios";
import { mockAnalyzeService } from "./mock";

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === "true";

const realAnalyzeService = {
  uploadFile: (file, onProgress) => {
    const formData = new FormData();
    formData.append("file", file);
    // TODO: 백엔드 targets 연동 후 아래 주석 해제
    // formData.append("targets", JSON.stringify(targets));
    return api.post("/api/v1/analyze", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: e => onProgress?.(Math.round((e.loaded / e.total) * 100)),
    });
  },
  analyzeUrl: (url) => api.post("/api/v1/analyze/url", { url }),  // ← /url 로 변경
  // TODO: analyzeUrl: (url, targets) => api.post("/api/v1/analyze/url", { url, targets }),
  getResult: (taskId) => api.get(`/api/v1/result/${taskId}`),
};

export const analyzeService = MOCK_MODE ? mockAnalyzeService : realAnalyzeService;