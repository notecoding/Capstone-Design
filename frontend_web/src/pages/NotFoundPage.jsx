
// src/pages/NotFoundPage.jsx
// 존재하지 않는 URL 접근 시 표시되는 404 페이지
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="flex flex-col items-center justify-center flex-1 py-20 text-center">
      <h1 className="text-7xl font-bold text-gray-200 mb-4">404</h1>
      <p className="text-gray-500 mb-8">페이지를 찾을 수 없습니다.</p>
      <Link
        to="/"
        className="px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
      >
        홈으로 돌아가기
      </Link>
    </main>
  );
}