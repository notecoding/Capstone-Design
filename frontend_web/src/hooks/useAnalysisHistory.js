// src/hooks/useAnalysisHistory.js
import { useState, useEffect, useRef } from "react";
import { loadHistory, clearHistory } from "../utils/history";

export default function useAnalysisHistory() {
  const [history, setHistory] = useState([]);
  const clearing = useRef(false);

  useEffect(() => {
    setHistory(loadHistory());
    const onUpdate = () => {
      if (clearing.current) return;
      setHistory(loadHistory());
    };
    window.addEventListener("history-updated", onUpdate);
    return () => window.removeEventListener("history-updated", onUpdate);
  }, []);

  const handleClear = () => {
    clearing.current = true;
    clearHistory();
    setHistory([]);
    setTimeout(() => { clearing.current = false; }, 100);
  };

  return { history, handleClear };
}