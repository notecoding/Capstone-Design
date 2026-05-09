# AI 영상 판별 시스템 — 가이드라인 v8

---

## 전체 흐름

```
STEP 1~3   로컬 환경 세팅 + 코드 교체 + 동작 확인  ← 완료
STEP 4     Colab 학습 1라운드                       ← 진행 중
STEP 5     성능 수치 측정
STEP 6     데이터 추가 + 2라운드 학습
STEP 7     Phase 추가
```

---

## 최종 폴더 구조

```
backend_api/
  ai_engine/
    src/
      config.py
      inference.py
      preprocess.py
      postprocess.py
      base.py
      __init__.py
    scripts/
      benchmark.py
      validate_thresholds.py
      __init__.py
    checkpoints/
      checkpoint_main.pth    ← 학습 후 Drive에서 다운로드해서 여기에
      README.txt
    requirements.txt
    test_run.py
  colab_train.py             ← Colab 셀에 붙여넣기용
```

---

## v7 → v8 변경사항

```
colab_train.py
  VideoFeatDataset   .squeeze() 추가
                     (1, 8, 768) → (8, 768) 차원 정리
                     DataLoader 배치 시 4D 텐서 에러 수정

  Real 영상 수집     rglob → iterdir 변경
                     Real 폴더가 하위 폴더 없이 바로 영상 파일 존재
                     rglob 사용 시 0개로 나오는 버그 수정
```

---

## STEP 1~3 — 완료

로컬 세팅, 파일 교체, test_run.py → status: success 확인 완료.

---

## STEP 4 — Colab 학습

### 셀 실행 순서

**셀 0 — pip 버전 고정 설치 (매 세션마다 필수)**
```
open_clip_torch==2.24.0 버전 고정
버전 다르면 API 불일치 발생 가능
```

**셀 1 — Drive 연결**
```
Drive 마운트
/content/drive/MyDrive/capstone/ 경로 생성됨
```

**셀 2 — 폴더 생성**
```
/content/data/
/content/drive/MyDrive/capstone/data/
/content/drive/MyDrive/capstone/ai_engine/checkpoints/
```

**셀 3 — 영상 다운로드 (코랩 로컬에 — Drive 아님)**
```
aria2c 멀티스레드 다운로드 (wget보다 빠름)
unzip -q 로 로그 최소화
GenVideo-Val.zip → /content/data/ 압축 해제 후 zip 삭제
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

폴더 구조 확인:
```
/content/data/GenVideo-Val/
  Fake/
    Crafter/   1398개
    Gen2/      1380개
    HotShot/    700개
    Lavie/     1400개
    ModelScope/ 700개
    MoonValley/ 626개
    MorphStudio/700개
    Show_1/     700개
    Sora/        56개   ← 가장 적음
    WildScrape/ 642개
  Real/
    msrvtt_*.mp4  10000개  ← 하위 폴더 없이 바로 파일 존재

__MACOSX/   ← macOS 메타데이터 폴더, 무시해도 됨
```

**셀 4 — colab_train.py 전체 붙여넣고 실행**

설정값 확인:
```
ROUND      = 1
N_PER_CAT  = 25    카테고리당 25개 → AI 총 250개
N_REAL     = 250   실제 영상 250개
EPOCHS     = 15
BATCH_SIZE = 32
```

### 학습 진행 출력

```
라운드: 1 | 캐시 버전: f8_ViT-L-14
GPU: Tesla T4
CLIP 로딩 완료
AI 카테고리 수: 10개
  Crafter: 25개 / Gen2: 25개 / ...
균형 조정 — AI: 250개 / 실제: 250개

AI 영상 특징 추출 중...
  50/250 (성공: 48)      ← 50개마다 출력
  100/250 (성공: 96)
  ...
추출 완료 — AI: 250개 / 실제: 250개
CLIP GPU 메모리 해제 완료

학습: 400개 / 검증: 100개 | 배치: 32
새로 학습 시작 — lr: 0.0001

Epoch  1/15 — 학습 Loss: 0.69 Acc: 55.0% | 검증 Loss: 0.71 Acc: 52.0%
Epoch  5/15 — 학습 Loss: 0.45 Acc: 78.0% | 검증 Loss: 0.50 Acc: 75.0%
Epoch 15/15 — 학습 Loss: 0.18 Acc: 94.0% | 검증 Loss: 0.33 Acc: 85.0%
1라운드 학습 완료
```

### 예상 소요 시간

```
CLIP 로딩:        1~2분
특징 추출 500개:  1~2시간  (이후 캐시 재사용)
학습 15 epoch:    30분~1시간
전체:             1.5~3시간
```

### 과적합 확인

```
정상    학습 Acc ↑  검증 Acc ↑  같이 올라감
과적합  학습 Acc ↑  검증 Acc ↓  내려가기 시작
        → val_loss 기준으로 최선 시점 자동 저장
```

### 세션 끊김 대비

```
특징 캐시가 Drive에 npz로 저장됨
세션 끊겨도 셀 0~2 재실행 후 셀 4 바로 실행
→ 캐시 발견 → 추출 스킵 → 바로 학습 재시작
영상 재다운로드 불필요
```

### 학습 완료 후

```
Drive → capstone/ai_engine/checkpoints/checkpoint_main.pth 다운로드
→ 로컬 ai_engine/checkpoints/ 에 넣기
```

---

## STEP 5 — 성능 수치 측정 (로컬)

### 실행

```bash
cd backend_api
python ai_engine/scripts/benchmark.py --base "C:/경로/직접수정"
```

### 목표 수치

```
전체 정확도   70% 이상
AI 탐지율     75% 이상
오탐률        20% 이하
F1 Score      0.70 이상
```

### 수치 미달 시

```
AI 탐지율 낮음  → config.py AI_THRESHOLD 0.50 → 0.45로 낮추기
오탐 많음       → AI_THRESHOLD 0.50 → 0.55로 올리기
전체적으로 낮음 → 2라운드 진행
```

---

## STEP 6 — 데이터 추가 + 2라운드 학습

### 2라운드 설정 변경

colab_train.py 상단 숫자만 바꾸면 나머지 자동:

```
ROUND      = 2    (1 → 2)
N_PER_CAT  = 50   (25 → 50)
N_REAL     = 500  (250 → 500)
```

자동으로 처리되는 것들:
```
이전 라운드 학습 파일 자동 제외   train_files_r1.json 읽어서 제외
이전 가중치 자동 로드             checkpoint_main.pth 불러옴
lr 자동으로 1/10 적용            1e-4 → 1e-5
고정 val 셋 자동 재사용           라운드 간 공정한 비교
```

### 라운드별 수치 기록표

| 라운드 | AI | 실제 | 정확도 | AI탐지율 | 오탐률 | F1 |
|---|---|---|---|---|---|---|
| 1라운드 | 250개 | 250개 | | | | |
| 2라운드 | 500개 | 500개 | | | | |
| 3라운드 | 필요 시 | | | | | |

---

## STEP 7 — Phase 추가

```
Phase A: FFT 심화
  inference.py _analyze_frequency() 수정
  GAN/Diffusion 격자 패턴까지 분석

Phase B: rPPG 생체 신호
  inference.py _analyze_rppg() 추가
  얼굴 있는 영상 한정, 혈류 신호 감지

Phase C: 물리 일관성
  inference.py _analyze_physics() 추가
  중력/관성/충돌 법칙 위반 감지
```

---

## 주의사항

### 학습 관련

```
T4 GPU 필수
  실행 전 torch.cuda.get_device_name(0) 확인
  K80이면 새 세션 받기

Drive 마운트 확인
  os.path.exists('/content/drive/MyDrive/capstone') → True 나와야 함

SAVE_PATH 반드시 Drive 경로
  /content/drive/MyDrive/... 로 시작해야 함
  /content/... 만 쓰면 세션 끊길 때 날아감

Colab 탭 유지
  90분 방치 시 세션 끊김
  가끔 탭 확인 필요
```

### 데이터 관련

```
AI:실제 = 1:1 자동 균형
  min_count로 자동 조정

Sora 카테고리 56개뿐
  2라운드 N_PER_CAT=50 해도 최대 56개까지만 나옴

__MACOSX 폴더
  무시해도 됨, 코드가 자동 제외

Real 폴더 구조
  하위 폴더 없이 바로 영상 파일 존재
  iterdir()로 수집 (rglob 쓰면 0개 나옴)
```

---

## Drive 저장 파일 목록

```
capstone/
  ai_engine/checkpoints/
    checkpoint_main.pth          가중치 ~30MB
  data/
    features_cache_r1_f8_ViT-L-14.npz   특징 캐시 ~12MB
    train_files_r1.json          학습 파일 목록
    val_files_r1.json            검증 파일 목록
    fixed_val.json               고정 val 셋 (라운드1에서 생성)
```

---

## 전체 체크리스트

```
완료
☑ STEP 1: 파일 교체 완료
☑ STEP 2: pip install 완료
☑ STEP 3: test_run.py → status: success 확인

진행 예정
□ STEP 4: T4 GPU 확인
□ STEP 4: 영상 다운로드 (aria2c)
□ STEP 4: 1라운드 학습 완료
□ STEP 4: checkpoint_main.pth 로컬 저장
□ STEP 5: benchmark.py → 수치 기록표 작성
□ STEP 6: 목표 미달 시 2라운드 학습
□ STEP 7: 시간 허락 시 Phase 추가
```

---

## 중요 결정사항 기록

```
CLIP Zero-shot 제거       텍스트 비교 → 프레임 유사도 방식
DeMamba 대체              환경 문제 → 광류 방식 대체
GenVideo-100K 포기        모델 ID 없음
GenVideo-Val 사용         검증용이지만 현실적 대안, train/val 직접 분리
fallback 방향             1 - avg_sim (유사도 낮을수록 AI 의심)
모델 구조 통일            inference.py = colab_train.py 동일 구조 필수
Real 폴더 수집 방식       rglob → iterdir (하위 폴더 없는 구조)
squeeze() 추가            (1,8,768) → (8,768) 4D 텐서 에러 수정
```

---

## 문제 발생 시

```
AssertionError 4-D tensor    VideoFeatDataset에 .squeeze() 있는지 확인
실제 영상 0개                Real 수집 시 iterdir() 쓰는지 확인
load_state_dict 에러         inference.py 모델 구조 = colab_train.py 확인
캐시 로드 후 경로 불일치     세션 재시작 후 동일 ROUND로 재실행
Drive 저장 실패              로컬에는 저장됨, Drive 마운트 재확인
수치 미달                    AI_THRESHOLD 조정 후 benchmark 재실행
Colab 느림                   T4 GPU 확인, K80이면 재할당
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
