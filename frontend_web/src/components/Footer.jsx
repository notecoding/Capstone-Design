// src/components/Footer.jsx
// 모든 페이지 하단에 공통으로 표시되는 푸터
// App.jsx 에서 <Footer /> 한 줄로 사용
export default function Footer() {
  return (
    <footer className="w-full border-t border-gray-200 px-6 py-4 text-center text-sm text-gray-400">
      © {new Date().getFullYear()} Capstone-Desgine. All rights reserved.
    </footer>
  );
}