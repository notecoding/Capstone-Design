ai 파트 부분

## 폴더 구조
```
ai_engine/
├── src/
│   ├── __init__.py          # 패키지 진입점
│   ├── inference.py         # ★ 백엔드가 import하는 파일 (이름 변경 금지)
│   ├── preprocess.py        # 프레임 추출 / evidence 저장
│   └── config.py            # 가중치/임계값/프롬프트 설정
├── models/                  # 학습 가중치 저장 (현재 비어있음, v3에서 사용)
├── requirements_ai.txt


## 빠른 시작

```bash
# 1. 패키지 설치
pip install -r requirements_ai.txt
winget install ffmpeg
winget --version 버전확인


## 백엔드와의 약속 (절대 변경 금지)

```python
# 백엔드 호출 코드 (이미 완성)
from ai_engine.src.inference import run_ai_video_analysis
result = run_ai_video_analysis(video_path, output_dir)
```

### 반환 JSON 구조
```json
{
  "status":     "success",
  "is_ai":      true,
  "confidence": 0.8231,
  "analysis_details": {
    "details":          "AI 생성 영상으로 판별되었습니다. 근거: CLIP: 평균 82%, ...",
    "detected_regions": []
  },
  "evidence_frames": [
    {"timestamp": 2.5, "file_name": "frame_2.5.jpg"},
    {"timestamp": 5.1, "file_name": "frame_5.1.jpg"}
  ]
}
```

### 에러 반환 구조
```json
{"status": "error", "message": "오류 내용"}
```
