export const TARGET_LIST = [
  { id: "face",   label: "얼굴 조작",   sub: "딥페이크 탐지" },
  { id: "bg",     label: "배경 생성",   sub: "AI 배경 판별" },
  { id: "motion", label: "움직임 패턴", sub: "부자연스러운 모션" },
  { id: "voice",  label: "음성 합성",   sub: "AI 목소리 탐지" },
];
// 기본값: 모두 true (타겟 미선택 시 전체 분석)
export const DEFAULT_TARGETS = { face: true, bg: true, motion: true, voice: true };
export const ALLOWED_EXT     = [".mp4", ".avi", ".mov"];
export const MAX_FILE_MB     = 500;
export const URL_PATTERN     = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be).+/i;