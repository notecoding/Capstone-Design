// src/api/axios.js
import axios from "axios";

// 로컬 개발 시 .env 의 VITE_API_URL 값을 읽어옴
// 없으면 127.0.0.1:8000 을 기본값으로 사용
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_URL,      // 모든 요청 URL 앞에 자동으로 붙음
  withCredentials: false, // 현재 백엔드가 세션 인증 없으므로 false
  timeout: 60000,         // AI 분석은 오래 걸리므로 60초로 늘림 (기존 10초)
  // Content-Type 은 여기서 고정하지 않음
  // → JSON 요청은 axios 가 자동으로 설정
  // → 파일 업로드(multipart) 는 services.js 에서 직접 지정
});

// ─── 요청 인터셉터 ────────────────────────────────────────────────
// 요청이 서버로 떠나기 직전에 실행됨
api.interceptors.request.use(
  (config) => {
    // localStorage에 accessToken 있으면 모든 요청 헤더에 자동으로 붙여줌
    const token = localStorage.getItem("accessToken");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── 응답 인터셉터 ────────────────────────────────────────────────
// 서버 응답이 컴포넌트에 도달하기 전에 실행됨
// 성공 시 response.data 만 꺼내서 반환 → 서비스에서 .data 반복 불필요
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status  = error.response?.status;
    const message = error.response?.data?.message || error.message;

    if (status === 401) {
      // 토큰 만료 → 로그인 페이지로 이동
      localStorage.removeItem("accessToken");
      window.location.href = "/login";
    } else if (status === 403) {
      console.warn("🚫 권한 없음:", message);
    } else if (status >= 500) {
      console.error("💥 서버 오류:", message);
    }

    return Promise.reject(error);
  }
);

export default api;