// src/App.jsx
// 라우팅 설정 파일
// 새 페이지 추가할 때 여기에 <Route> 한 줄 추가하면 됨
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import HomePage from "./pages/HomePage";
import NotFoundPage from "./pages/NotFoundPage";
import ResultPage from "./pages/ResultPage";

export default function App() {
  return (
    <BrowserRouter>
      {/* 모든 페이지에 공통으로 Navbar, Footer 표시 */}
      <div className=" min-h-screen flex flex-col">
        <Navbar />

        {/* 페이지 컨텐츠 영역 - Routes 안에 페이지 추가 */}
        <div className="flex-1 bg-gray-100">
          <Routes>
            <Route path="/" element={<HomePage />} />
            {/* 새 페이지 추가 예시 */}
            {/* <Route path="/about" element={<AboutPage />} /> */}
            <Route path="/result/:taskId" element={<ResultPage />} />
            {/* 위 경로에 해당하지 않으면 404 페이지 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>

        <Footer />
      </div>
    </BrowserRouter>
  );
}
