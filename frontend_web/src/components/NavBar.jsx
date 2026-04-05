// src/components/Navbar.jsx
// 모든 페이지 상단에 공통으로 표시되는 네비게이션 바
// App.jsx 에서 <Navbar /> 한 줄로 사용
import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="w-full bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      {/* 로고 - 클릭 시 홈으로 이동 */}
      <Link to="/" className="text-3xl font-bold ">
        TrueView
      </Link>

      {/* 네비게이션 링크 - 필요한 페이지 추가/삭제 */}
      <div className="flex gap-6">
        <Link to="/" className="text-gray-600 hover:text-gray-900 transition-colors">
          홈
        </Link>
        {/* <Link to="/about">소개</Link> */}
        
      </div>
    </nav>
  );
}