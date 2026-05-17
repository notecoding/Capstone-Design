# AI Video Detection Backend

AI 기반 영상 조작 탐지 서비스의 백엔드 서버입니다.

## 주요 기능

- 영상 파일 업로드 분석
- URL 기반 영상 다운로드 및 분석
- Celery 기반 비동기 분석 처리
- Redis 기반 작업 상태 관리
- 분석 진행 상태 세분화
- 선택 타겟 기반 분석 모듈 분기
- 모듈별 점수 응답 제공
- 증거 프레임 이미지 URL 제공
- 실패 상황별 에러 코드 제공
- 환경변수 기반 실행 설정

## 폴더 구조

```text
backend_api/
├─ main.py
├─ app/
│  ├─ api/
│  │  └─ analysis.py
│  ├─ worker.py
│  ├─ settings.py
│  └─ services/
├─ ai_engine/
│  └─ src/
│     ├─ inference.py
│     ├─ postprocess.py
│     ├─ preprocess.py
│     ├─ base.py
│     └─ config.py
├─ storage/
│  ├─ uploads/
│  └─ results/
├─ requirements.txt
├─ .env.example
└─ README.md
실행 준비
pip install -r requirements.txt
cp .env.example .env
Redis 실행
redis-server
FastAPI 실행
uvicorn main:app --reload
Celery Worker 실행
celery -A app.worker worker --loglevel=info
헬스체크
GET /api/v1/health

정상 응답 예시:

{
  "status": "ok",
  "api": "running",
  "redis": "connected",
  "storage": {
    "storage_dir": true,
    "upload_dir": true,
    "result_dir": true
  },
  "max_upload_size_mb": 500
}
파일 분석 요청
POST /api/v1/analyze

요청 형식:

multipart/form-data

필드:

file: 영상 파일
targets: ["face", "motion", "background", "voice"]

응답 예시:

{
  "task_id": "작업 ID",
  "status": "queued",
  "progress": 0,
  "message": "분석 작업이 대기열에 등록되었습니다."
}
URL 분석 요청
POST /api/v1/analyze/url

요청 예시:

{
  "url": "https://example.com/video.mp4",
  "targets": ["face", "motion"]
}
결과 조회
GET /api/v1/result/{task_id}

진행 중 응답 예시:

{
  "task_id": "작업 ID",
  "status": "analyzing_clip",
  "progress": 40,
  "message": "프레임 유사도 기반 분석을 진행하는 중입니다.",
  "selected_targets": ["face"],
  "selected_analyzers": ["clip"]
}

완료 응답 예시:

{
  "task_id": "작업 ID",
  "status": "completed",
  "progress": 100,
  "message": "AI 분석이 완료되었습니다.",
  "result": {
    "status": "success",
    "is_ai": true,
    "confidence": 0.82,
    "overall_score": 0.82,
    "label": "위험",
    "module_scores": {
      "clip": 0.91,
      "temporal": 0.77,
      "frequency": 0.64,
      "metadata": 0.85
    },
    "evidence_frames": [
      {
        "timestamp": 4.17,
        "time": 4.17,
        "file_name": "frame_4_17.jpg",
        "image_url": "/storage/results/task_id/frame_4_17.jpg",
        "probability": 0.88,
        "score": 0.88,
        "reason": "AI 조작 가능성이 높은 구간으로 선택된 증거 프레임입니다.",
        "tags": []
      }
    ]
  }
}

실패 응답 예시:

{
  "task_id": "작업 ID",
  "status": "failed",
  "progress": 100,
  "error_code": "VIDEO_TOO_SHORT",
  "message": "영상이 너무 짧음",
  "result": null
}
타겟 매핑
face → clip
motion → temporal
background → frequency
voice → metadata

현재 voice는 실제 음성 분석 모듈이 없기 때문에 metadata 분석에 임시 연결되어 있습니다.

주요 에러 코드
INVALID_URL
DOWNLOAD_FAILED
DOWNLOAD_FILE_NOT_FOUND
FILE_NOT_FOUND
UNSUPPORTED_FORMAT
VIDEO_TOO_SHORT
VIDEO_TOO_LONG
FRAME_EXTRACTION_FAILED
ANALYSIS_FAILED
URL_ANALYSIS_FAILED
WORKER_FAILED

가장 쉬운 실행 요약 <br />
터미널 1 <br />
redis-server <br />
터미널 2 <br />
cd C:\Users\cow25\Desktop\capstorn\backend_api <br />
python -m celery -A app.worker.app worker --loglevel=info --pool=solo <br />
터미널 3 <br />
cd C:\Users\cow25\Desktop\capstorn\backend_api <br />
python -m uvicorn main:app --reload <br />
터미널 4 <br />
cd C:\Users\cow25\Desktop\capstorn\frontend_web <br />
npm install <br />
npm run dev <br />

pip install fastapi uvicorn celery redis yt-dlp open-clip-torch opencv-python pillow numpy python-multipart
