// src/api/axios.js
import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_URL,
  withCredentials: false,
  timeout: 60000,
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message;
    const status  = error.response?.status;

    if (status >= 500) {
      console.error("서버 오류:", message);
    }

    return Promise.reject(error);
  }
);

export default api;