// src/App.jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { NavBar, Footer } from "./components/layout";
import HomePage           from "./pages/HomePage";
import ResultPage         from "./pages/ResultPage";
import NotFoundPage       from "./pages/NotFoundPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <NavBar />
        <div className="flex-1">
          <Routes>
            <Route path="/"               element={<HomePage />} />
            <Route path="/result/:taskId" element={<ResultPage />} />
            <Route path="*"               element={<NotFoundPage />} />
          </Routes>
        </div>
        <Footer />
      </div>
    </BrowserRouter>
  );
}