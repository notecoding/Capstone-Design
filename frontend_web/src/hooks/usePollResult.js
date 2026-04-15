// src/hooks/usePollResult.js
import { useState, useEffect, useRef } from "react";
import { analyzeService } from "../api/analyzeService";

const STEP_DELAY_MS = 600;
const TOTAL_TASKS   = 4;

export default function usePollResult(taskId, options = {}) {
  const { initialResult } = options;  // 기록에서 넘어온 결과

  const [result,     setResult]     = useState(initialResult || null);
  const [taskStatus, setTaskStatus] = useState(initialResult ? "completed" : "pending");
  const [message,    setMessage]    = useState("분석 결과를 불러오는 중입니다.");
  const [error,      setError]      = useState("");

  const pendingResult = useRef(null);
  const stopped       = useRef(false);

  useEffect(() => {
    // 기록에서 넘어온 경우 폴링 스킵
    if (initialResult) return;
    if (!taskId) { setError("잘못된 접근입니다."); return; }

    stopped.current = false;
    let intervalId  = null;

    const fetch = async () => {
      try {
        const res = await analyzeService.getResult(taskId);
        if (stopped.current) return;

        const status = res.status === "started" ? "processing" : res.status;
        setTaskStatus(status);

        if (status === "pending")    { setMessage(res.message || "작업 대기 중입니다."); return; }
        if (status === "processing") { setMessage(res.message || "AI 분석이 진행 중입니다."); return; }

        if (status === "completed") {
          clearInterval(intervalId);
          pendingResult.current = res.result;
          setTaskStatus("completing");
          setTimeout(() => {
            if (!stopped.current) setResult(pendingResult.current);
          }, TOTAL_TASKS * STEP_DELAY_MS + 400);
          return;
        }

        if (status === "failed") {
          setError(res.message || "분석에 실패했습니다.");
          clearInterval(intervalId);
        }
      } catch (err) {
        setError(err.response?.data?.message || "결과를 불러오지 못했습니다.");
        clearInterval(intervalId);
      }
    };

    fetch();
    intervalId = setInterval(fetch, 2000);
    return () => { stopped.current = true; clearInterval(intervalId); };
  }, [taskId, initialResult]);

  return { result, taskStatus, message, error };
}