// src/api/mock.js
export const MOCK_SCENARIO = "danger"; // "warn" | "safe"

const FRAME_IMGS = [
  "https://picsum.photos/seed/frame1/640/360",
  "https://picsum.photos/seed/frame2/640/360",
  "https://picsum.photos/seed/frame3/640/360",
];

const SCENARIOS = {
  danger: {
    task_id: "mock-task-danger",
    status:  "completed",
    result: {
      status:     "success",
      is_ai:      true,
      confidence: 0.91,
      analysis_details: {
        details:
          "AI 생성 영상으로 판별되었습니다. 근거: CLIP 평균 91.2%, 표준편차 0.042 / " +
          "시공간 분석: 이동불일치=0.821, 방향불일치=0.743, 텍스처 이상=0.698",
        // 분석기별 점수 (타겟별 위험도 테이블용)
        analyzer_scores: [
          { key: "face",     label: "얼굴 조작",   score: 0.87, tags: ["얼굴 경계 왜곡", "눈 깜빡임 이상", "피부 텍스처 불일치"] },
          { key: "bg",       label: "배경 생성",   score: 0.73, tags: ["텍스처 반복 패턴", "엣지 블러"] },
          { key: "motion",   label: "움직임 패턴", score: 0.62, tags: ["광류 방향 불일치", "이동량 불규칙"] },
          { key: "voice",    label: "음성 합성",   score: 0.18, tags: ["이상 없음"] },
          { key: "metadata", label: "메타데이터",  score: 0.25, tags: ["정상 인코더", "C2PA 없음"] },
        ],
        detected_regions: [
          { issue: "얼굴 경계 왜곡",     x: 120, y: 80,  width: 200, height: 220 },
          { issue: "눈 깜빡임 패턴 이상", x: 145, y: 110, width: 80,  height: 40  },
          { issue: "피부 텍스처 불일치",  x: 130, y: 150, width: 160, height: 120 },
        ],
      },
      duration: 32,  // 영상 총 길이(초) — 타임라인 포인트 위치 계산용
      evidence_frames: [
        {
          timestamp:   3.2,
          path:        FRAME_IMGS[0],
          probability: 0.94,
          tags:        ["얼굴 경계 왜곡", "GAN 아티팩트", "피부 텍스처 이상"],
        },
        {
          timestamp:   12.8,
          path:        FRAME_IMGS[1],
          probability: 0.89,
          tags:        ["눈 깜빡임 패턴 이상", "광원 불일치"],
        },
        {
          timestamp:   27.1,
          path:        FRAME_IMGS[2],
          probability: 0.76,
          tags:        ["배경 텍스처 반복", "엣지 블러"],
        },
      ],
    },
  },

  warn: {
    task_id: "mock-task-warn",
    status:  "completed",
    result: {
      status:     "success",
      is_ai:      false,
      confidence: 0.55,
      analysis_details: {
        details:
          "AI 생성 가능성이 일부 감지되었습니다. 확실하지 않으므로 추가 확인이 필요합니다. " +
          "근거: CLIP 평균 54.8% / 시공간 분석: 방향불일치=0.412, 엣지 이상=0.389",
        analyzer_scores: [
          { key: "face",     label: "얼굴 조작",   score: 0.42, tags: ["경미한 경계 흐림"] },
          { key: "bg",       label: "배경 생성",   score: 0.61, tags: ["텍스처 반복 패턴", "조명 불일치"] },
          { key: "motion",   label: "움직임 패턴", score: 0.48, tags: ["이동량 불규칙"] },
          { key: "voice",    label: "음성 합성",   score: 0.22, tags: ["이상 없음"] },
          { key: "metadata", label: "메타데이터",  score: 0.20, tags: ["이상 없음"] },
        ],
        detected_regions: [
          { issue: "배경 텍스처 반복 패턴", x: 0,   y: 200, width: 640, height: 160 },
          { issue: "조명 방향 불일치",       x: 200, y: 50,  width: 120, height: 100 },
        ],
      },
      duration: 45,
      evidence_frames: [
        { timestamp: 8.4,  path: FRAME_IMGS[0], probability: 0.61, tags: ["배경 텍스처 반복"] },
        { timestamp: 19.2, path: FRAME_IMGS[1], probability: 0.53, tags: ["조명 불일치"] },
      ],
    },
  },

  safe: {
    task_id: "mock-task-safe",
    status:  "completed",
    result: {
      status:     "success",
      is_ai:      false,
      confidence: 0.12,
      analysis_details: {
        details:
          "실제 촬영 영상으로 판별되었습니다. 자연스러운 노이즈 패턴과 정상적인 움직임이 확인되었습니다. " +
          "근거: CLIP 평균 12.1% / 시공간 분석: 모든 지표 정상 범위",
        analyzer_scores: [
          { key: "face",     label: "얼굴 조작",   score: 0.10, tags: ["이상 없음"] },
          { key: "bg",       label: "배경 생성",   score: 0.15, tags: ["이상 없음"] },
          { key: "motion",   label: "움직임 패턴", score: 0.08, tags: ["이상 없음"] },
          { key: "voice",    label: "음성 합성",   score: 0.12, tags: ["이상 없음"] },
          { key: "metadata", label: "메타데이터",  score: 0.10, tags: ["이상 없음"] },
        ],
        detected_regions: [],
      },
      duration: 28,
      evidence_frames: [],
    },
  },
};

function mockUploadProgress(onProgress) {
  return new Promise((resolve) => {
    let pct = 0;
    const t = setInterval(() => {
      pct += Math.floor(Math.random() * 20) + 10;
      if (pct >= 100) { clearInterval(t); onProgress?.(100); resolve(); }
      else onProgress?.(pct);
    }, 150);
  });
}

export const mockAnalyzeService = {
  _callCount: 0,

  uploadFile: async (file, onProgress) => {
    await mockUploadProgress(onProgress);
    return { task_id: SCENARIOS[MOCK_SCENARIO].task_id, status: "processing" };
  },

  analyzeUrl: async (_url) => {
    await new Promise((r) => setTimeout(r, 500));
    return { task_id: SCENARIOS[MOCK_SCENARIO].task_id, status: "processing" };
  },

  getResult: async (_taskId) => {
    mockAnalyzeService._callCount += 1;
    if (mockAnalyzeService._callCount <= 2) {
      await new Promise((r) => setTimeout(r, 800));
      return { task_id: SCENARIOS[MOCK_SCENARIO].task_id, status: "processing", message: "AI 분석이 진행 중입니다." };
    }
    await new Promise((r) => setTimeout(r, 1000));
    mockAnalyzeService._callCount = 0;
    return SCENARIOS[MOCK_SCENARIO];
  },
};