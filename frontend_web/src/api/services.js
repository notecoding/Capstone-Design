// src/api/services.js
import api from "./axios";

// ─── 사용법 ───────────────────────────────────────────────────────
// 새 서비스 추가할 때 아래 패턴을 복붙하고 이름이랑 엔드포인트만 바꾸면 됨
// 컴포넌트에서: import { postService } from "../api/services"

// ─── 게시글 (템플릿 - 복붙 후 이름/엔드포인트 수정) ──────────────
export const analyzeService = {
 
  // 파일 업로드 분석
  // 사용 예) analyzeService.uploadFile(file, (pct) => setProgress(pct))
  uploadFile: (file, onProgress) => {
    const formData = new FormData();
    formData.append("file", file);
 
    return api.post("/api/v1/analyze", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        const pct = Math.round((e.loaded / e.total) * 100);
        onProgress?.(pct);
      },
    });
  },
 
  // URL 분석
  // 사용 예) analyzeService.analyzeUrl("https://youtube.com/...")
  analyzeUrl: (url) => api.post("/api/v1/analyze-url", { url }),
 
  // 결과 조회 (폴링용)
  // 사용 예) analyzeService.getResult("task-id-123")
  getResult: (taskId) => api.get(`/api/v1/result/${taskId}`),
};

// ─── 새 서비스는 여기 아래에 추가 ────────────────────────────────
// export const userService = {
//   getList:  (params)     => api.get("/users", { params }),
//   getById:  (id)         => api.get(`/users/${id}`),
//   create:   (data)       => api.post("/users", data),
//   update:   (id, data)   => api.put(`/users/${id}`, data),
//   delete:   (id)         => api.delete(`/users/${id}`),
// };