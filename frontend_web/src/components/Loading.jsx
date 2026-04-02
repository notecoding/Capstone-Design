// src/components/Loading.jsx
// 데이터 로딩 중일 때 표시하는 스피너
// 사용 예) if (loading) return <Loading />
export default function Loading() {
  return (
    <div className="flex items-center justify-center w-full py-20">
      <div className="w-8 h-8 border-4 border-gray-200 border-t-gray-800 rounded-full animate-spin" />
    </div>
  );
}