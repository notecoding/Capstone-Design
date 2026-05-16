// src/api/analyzeService.js
import api from "./axios";
import { mockAnalyzeService } from "./mock";

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === "true";

const realAnalyzeService = {
  uploadFile: (file, targets, onProgress) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("targets", JSON.stringify(targets ?? []));
    return api.post("/api/v1/analyze", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: e => onProgress?.(Math.round((e.loaded / e.total) * 100)),
    });
  },
  analyzeUrl: (url, targets) => api.post("/api/v1/analyze/url", { url, targets: targets ?? [] }),
  getResult: (taskId) => api.get(`/api/v1/result/${taskId}`),
};

export const analyzeService = MOCK_MODE ? mockAnalyzeService : realAnalyzeService;