# TrueView — AI 영상 판별 서비스

> "이 영상, 진짜일까요?" — 딥페이크·AI 생성 영상을 몇 초 만에 탐지합니다.

---

## 목차

1. [서비스 소개](#서비스-소개)
2. [기술 스택](#기술-스택)
3. [프로젝트 구조](#프로젝트-구조)
4. [시작하기](#시작하기)
5. [환경 변수](#환경-변수)
6. [목업 모드](#목업-모드)
7. [명명 규칙](#명명-규칙)
8. [API 연동](#api-연동)
9. [디자인 시스템](#디자인-시스템)
10. [향후 작업](#향후-작업)

---

## 서비스 소개

TrueView는 영상 파일 또는 YouTube URL을 업로드하면 AI가 딥페이크·AI 생성 여부를 자동으로 분석하는 웹 서비스입니다.

| 기능 | 설명 |
|---|---|
| 영상 업로드 | 드래그앤드롭 또는 파일 선택 (MP4, AVI, MOV / 최대 500MB) |
| URL 분석 | YouTube 링크 직접 입력 |
| 분석 타겟 선택 | 얼굴 조작 / 배경 생성 / 움직임 패턴 / 음성 합성 |
| 분석 중 화면 | 단계별 타임라인 + 진행률 게이지 + 선택 타겟 기준 작업 목록 |
| 결과 시각화 | AI 생성 확률 게이지, 의심 프레임 타임라인, 분석 상세 테이블 |
| 의심 구간 클릭 | 타임라인 포인트 클릭 시 해당 프레임 캡처 + 태그 표시 |
| 분석 기록 | 쿠키 기반 최근 10건 자동 저장 (30일) / 클릭 시 결과 페이지 이동 |

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| 프레임워크 | React 19 + Vite |
| 스타일 | Tailwind CSS v4 + CSS 변수 |
| 라우팅 | React Router DOM v7 |
| HTTP | Axios |
| 상태 관리 | React Hooks (useState, useEffect, useRef) |
| 저장소 | Cookie (분석 기록) |

---

## 프로젝트 구조

```
src/
├── api/
│   ├── axios.js               # Axios 인스턴스 + 인터셉터
│   ├── analyzeService.js      # API 서비스 (MOCK_MODE 전환)
│   └── mock.js                # 목업 데이터 (danger / warn / safe 3가지 시나리오)
│
├── components/
│   ├── common/
│   │   ├── Loading.jsx        # 로딩 스피너
│   │   ├── ErrorMessage.jsx   # 에러 메시지
│   │   └── index.js
│   ├── layout/
│   │   ├── NavBar.jsx         # 상단 네비게이션
│   │   ├── Footer.jsx         # 하단 푸터
│   │   └── index.js
│   ├── upload/
│   │   ├── VideoUpload.jsx    # 업로드 카드 (조립)
│   │   ├── DropZone.jsx       # 드래그앤드롭 영역
│   │   ├── TargetSelector.jsx # 분석 타겟 체크박스
│   │   └── index.js
│   ├── result/
│   │   ├── AnalyzingScreen.jsx  # 분석 중 화면 (단계 + 진행률 + 작업 목록)
│   │   ├── VerdictBanner.jsx    # 판정 결과 배너
│   │   ├── ConfidenceGauge.jsx  # AI 생성 확률 게이지
│   │   ├── AnalysisTimeline.jsx # 의심 구간 타임라인
│   │   ├── AnalysisTable.jsx    # 분석기별 상세 테이블
│   │   ├── ShareCard.jsx        # 결과 공유 + 피드백
│   │   └── index.js
│   └── history/
│       ├── AnalysisHistory.jsx  # 분석 기록 목록
│       ├── HistoryItem.jsx      # 기록 단일 아이템 (클릭 → 결과 페이지)
│       └── index.js
│
├── constants/
│   ├── targets.js   # TARGET_LIST, ALLOWED_EXT, URL_PATTERN 등
│   └── verdict.js   # VERDICT_CONFIG, getVerdict(), getScoreColor(), ANALYSIS_STEPS
│
├── hooks/
│   ├── useFetch.js            # 범용 데이터 페칭 훅
│   ├── usePollResult.js       # 분석 결과 폴링 (최소 표시 시간 보장)
│   └── useAnalysisHistory.js  # 쿠키 기록 상태 관리
│
├── pages/
│   ├── HomePage.jsx      # 메인 페이지
│   ├── ResultPage.jsx    # 분석 결과 페이지
│   └── NotFoundPage.jsx  # 404 페이지
│
├── utils/
│   └── history.js   # 쿠키 읽기/쓰기/삭제 유틸
│
├── App.jsx      # 라우팅
├── index.css    # Tailwind + CSS 변수 + 컴포넌트 클래스
└── main.jsx     # 진입점
```

---

## 시작하기

### 전체 서버 실행 순서

```bash
# 터미널 1 — Redis
redis-server

# 터미널 2 — Celery
cd C:\WebProject\Capstone-Design\backend_api
python -m celery -A app.worker.app worker --loglevel=info --pool=solo

# 터미널 3 — FastAPI
cd C:\WebProject\Capstone-Design\backend_api
python -m uvicorn main:app --reload

# 터미널 4 — 프론트엔드
cd C:\WebProject\Capstone-Design\frontend_web
npm install
npm run dev
```

### 프론트 단독 실행 (목업 모드)

```bash
cd C:\WebProject\Capstone-Design\frontend_web
npm run dev
```

> `.env` 에 `VITE_MOCK_MODE=true` 설정 필요

---

## 환경 변수

프로젝트 루트에 `.env` 파일을 생성합니다.

```bash
# 백엔드 실제 연동 시
VITE_MOCK_MODE=false
VITE_API_URL=http://127.0.0.1:8000

# 프론트 단독 실행 시
VITE_MOCK_MODE=true
VITE_API_URL=http://127.0.0.1:8000
```

| 변수 | 기본값 | 설명 |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | 백엔드 API Base URL |
| `VITE_MOCK_MODE` | `false` | `true`로 설정하면 목업 데이터로 동작 |

> ⚠️ `.env` 파일은 `.gitignore`에 추가하세요.

---

## 목업 모드

`src/api/mock.js` 상단의 `MOCK_SCENARIO` 값으로 시나리오 전환.

```js
export const MOCK_SCENARIO = "danger"; // "warn" | "safe"
```

| 값 | 결과 | 확률 |
|---|---|---|
| `"danger"` | 🔴 AI 의심 | 91% |
| `"warn"` | 🟡 주의 | 55% |
| `"safe"` | 🟢 정상 | 12% |

---

## 명명 규칙

| 대상 | 규칙 | 예시 |
|---|---|---|
| 컴포넌트 파일 | PascalCase.jsx | `NavBar.jsx`, `VideoUpload.jsx` |
| JS 유틸 / 훅 / 서비스 | camelCase.js | `analyzeService.js`, `usePollResult.js` |
| 폴더 | camelCase | `common/`, `upload/`, `result/` |
| 컴포넌트 함수 | PascalCase | `export default function NavBar()` |
| 커스텀 훅 | camelCase (use 접두사) | `export default function usePollResult()` |
| 상수 | UPPER_SNAKE_CASE | `TARGET_LIST`, `VERDICT_CONFIG` |
| 일반 변수 | camelCase | `taskId`, `fileName` |

---

## API 연동

### 엔드포인트

| 메서드 | URL | 설명 |
|---|---|---|
| `POST` | `/api/v1/analyze` | 파일 업로드 → `task_id` 반환 |
| `POST` | `/api/v1/analyze/url` | YouTube URL 분석 → `task_id` 반환 |
| `GET` | `/api/v1/result/:taskId` | 분석 결과 폴링 |

### 결과 응답 구조

```json
{
  "task_id": "550e8400-...",
  "status": "completed",
  "result": {
    "status": "success",
    "is_ai": true,
    "confidence": 0.91,
    "duration": 32,
    "analysis_details": {
      "details": "AI 생성 영상으로 판별되었습니다.",
      "analyzer_scores": [
        { "key": "face", "label": "얼굴 조작", "score": 0.87, "tags": ["얼굴 경계 왜곡"] }
      ],
      "detected_regions": []
    },
    "evidence_frames": [
      { "timestamp": 3.2, "file_name": "frame_3.2.jpg", "probability": 0.94, "tags": [] }
    ]
  }
}
```

### 이미지 URL 조합 방식

`evidence_frames[].file_name` 기준으로 프론트에서 URL을 조합합니다.

```
http://127.0.0.1:8000/storage/results/{task_id}/{file_name}
```

> 백엔드에 정적 파일 서빙(`/storage` 마운트) 필요 — 백엔드 명세서 참고

### 분석 타겟 (백엔드 연동 예정)

`src/api/analyzeService.js` TODO 주석 해제 시 즉시 연동됩니다.

---

## 디자인 시스템

### 컬러 토큰

| 변수 | 값 | 용도 |
|---|---|---|
| `--brand` | `#D85A30` | 주요 포인트 |
| `--brand-light` | `#FEF9F5` | 연한 배경 |
| `--bg` | `#FFFDF9` | 페이지 배경 |
| `--surface` | `#ffffff` | 카드 배경 |
| `--border` | `#EDE8DF` | 테두리 |
| `--text-1` | `#1C1917` | 본문 |
| `--text-2` | `#78716C` | 보조 |
| `--text-3` | `#A8A29E` | 힌트 |

### 컴포넌트 클래스

```css
.card        /* 카드 (흰 배경 + 테두리 + 라운드) */
.btn-brand   /* 브랜드 버튼 */
.btn-ghost   /* 고스트 버튼 */
.btn-sm      /* 작은 버튼 */
.sec-label   /* 섹션 레이블 */
.divider     /* 구분선 */
```

---

## 향후 작업

- [ ] 분석 타겟 백엔드 연동 (`analyzeService.js` TODO 주석 해제)
- [ ] 백엔드 정적 파일 서빙 추가 (의심 프레임 이미지 표시)


---

## 라이선스

© 2025 TrueView. Capstone Design Project.