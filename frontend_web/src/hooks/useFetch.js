// src/hooks/useFetch.js
// 데이터를 불러올 때 매번 반복되는 loading/error/data 상태 관리를 한 번에 처리하는 훅
//
// 사용 예)
// const { data, loading, error, refetch } = useFetch(() => postService.getList());
//
// refetch() 를 호출하면 데이터를 다시 불러옴

import { useState, useEffect, useCallback } from "react";

export default function useFetch(fetchFn) {
  const [data, setData] = useState(null);       // 서버에서 받아온 데이터
  const [loading, setLoading] = useState(true); // 로딩 상태
  const [error, setError] = useState(null);     // 에러 메시지

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.response?.data?.message || "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  // 컴포넌트 마운트 시 자동으로 데이터 불러옴
  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}