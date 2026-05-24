ai 파트 부분

## 반드시 반드시 checkpoints 폴더에 가중치 파일을 넣고 ai영상 판별을 해야됨

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
```

> v8 추가 파일
```
ai_engine/
├── src/
│   ├── base.py              # AnalyzerResult dataclass (분석기 표준 인터페이스)
│   ├── postprocess.py       # 결과 조립 + 증거 프레임 저장
├── scripts/                 # 개발/검증용 (실제 서비스에 불필요)
│   ├── benchmark.py         # 성능 수치 측정
│   └── validate_thresholds.py  # 시공간 임계값 검증
├── checkpoints/
│   └── checkpoint_main.pth  # 학습된 가중치 (학습 후 여기에 넣기)
├── README.md
├── test_run.py              # 단일 영상 테스트용
```


## 빠른 시작

```bash
# 1. 패키지 설치
pip install -r requirements_ai.txt
winget install ffmpeg
winget --version 버전확인
```

> v8 추가: 가상환경 사용 권장
```bash
# 가상환경 생성 및 활성화 (Windows)
python -m venv venv
venv\Scripts\activate

# 패키지 설치
pip install -r ai_engine/requirements.txt

# 비활성화
deactivate
```


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

> v8 추가: 반환값에 필드 추가됨
```json
{
  "status":     "success",
  "is_ai":      true,
  "confidence": 0.5449,
  "analysis_details": {
    "details":          "AI 생성 영상으로 판별되었습니다. 근거: ...",
    "detected_regions": []
  },
  "evidence_frames": [
    {"timestamp": 0.87, "file_name": "frame_0.87.jpg", "probability": 0.0291},
    {"timestamp": 0.57, "file_name": "frame_0.57.jpg", "probability": 0.0207},
    {"timestamp": 0.73, "file_name": "frame_0.73.jpg", "probability": 0.0155}
  ],
  "duration": 9.8
}
```
> `evidence_frames`에 `probability` 필드 추가 (프레임별 AI 의심도)
> `duration` 필드 추가 (영상 길이, 초 단위)


## 시스템 구조 (v8)

4개 분석기를 가중 평균으로 앙상블합니다.

```
CLIP (DeCoF Transformer)   핵심 — 학습 기반, 가중치 0.45
시공간 분석 (Optical Flow) 보조 — 룰베이스, 가중치 0.35
FFT 주파수 분석            보조 — 룰베이스, 가중치 0.15
메타데이터 분석            보조 — 룰베이스, 가중치 0.05
```

CLIP은 프레임 벡터 시퀀스를 Transformer에 입력해서 AI 확률을 산출합니다 (DeCoF 방식).
가중치 파일(`checkpoint_main.pth`)이 없으면 유사도 기반 fallback으로 자동 동작합니다.


## 학습 결과 (1라운드)

```
데이터셋: GenVideo-Val (AI 250개 + 실제 250개)
모델: ViT-L-14 + TransformerEncoder 2layer + MLP
```

```
전체 정확도: 99.2%
AI 탐지율:   98.6%
오탐률:       0.0%
F1 Score:     0.99
```


## 가중치 파일 설정

학습 완료 후 `checkpoint_main.pth`를 아래 경로에 넣으면 자동으로 로드됩니다.

```
ai_engine/checkpoints/checkpoint_main.pth
```

파일이 없으면 fallback 모드로 동작합니다 (성능 저하).


## 실행 위치 주의

반드시 `backend_api` 폴더에서 실행해야 합니다.

```bash
cd backend_api
python ai_engine/test_run.py
```

`ai_engine` 폴더 안에서 실행하면 `ModuleNotFoundError: No module named 'ai_engine'` 에러가 납니다.

참고문헌 및 출처
논문

DeCoF: Generated Video Detection via Frame Consistency
Ma et al., 2024
https://arxiv.org/abs/2402.02085

CLIP 프레임 간 유사도 기반 AI 영상 탐지 방법론 참고


DeMamba: AI-Generated Video Detection on Million-Scale GenVideo Benchmark
Chen et al., 2024
https://arxiv.org/abs/2405.19707

GenVideo 데이터셋 출처 및 탐지 벤치마크 참고



데이터셋

GenVideo-Val
출처: https://modelscope.cn/datasets/cccnju/Gen-Video
제공: DeMamba 논문 저자 (cccnju)
구성: Fake 10개 카테고리 8302개 / Real(MSRVTT) 10000개
카테고리: Crafter, Gen2, HotShot, Lavie, ModelScope,
MoonValley, MorphStudio, Show_1, Sora, WildScrape

모델

CLIP ViT-L/14
출처: OpenAI
https://github.com/openai/CLIP
라이선스: MIT
open_clip
출처: https://github.com/mlfoundations/open_clip
라이선스: MIT
