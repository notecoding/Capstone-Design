// src/components/ErrorMessage.jsx
// API 요청 실패 등 에러 발생 시 표시하는 컴포넌트
//
// 사용 예)
// if (error) return <ErrorMessage message={error} />
// <ErrorMessage message="데이터를 불러오지 못했습니다." />

export default function ErrorMessage({ message = "오류가 발생했습니다." }) {
  return (
    <div className="flex items-center gap-2 text-red-500 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm">
      <span>⚠️</span>
      <span>{message}</span>
    </div>
  );
}