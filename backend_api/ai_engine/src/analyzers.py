"""
ai_engine/src/analyzers.py
분석기 모듈 - BaseAnalyzer 추상 클래스와 3개 구현체

구조:
  BaseAnalyzer         ← 모든 분석기가 상속하는 공통 인터페이스
  ├── CLIPAnalyzer     ← 핵심 (가중치 55%), Zero-shot 판별
  ├── FrequencyAnalyzer← 보조 (가중치 30%), FFT 주파수 아티팩트
  └── MetadataAnalyzer ← 보조 (가중치 15%), 인코더 이름 / C2PA

v2에서 새 분석기 추가하는 법:
  1. BaseAnalyzer 상속해서 analyze() 구현
  2. config.py의 ANALYZER_WEIGHTS에 키/가중치 추가
  3. inference.py의 _ANALYZERS 딕셔너리에 등록
"""
from __future__ import annotations

import subprocess
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from .config import CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG


# ─────────────────────────────────────────────────────────────────────────────
# 공통 결과 타입
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalyzerResult:
    score: float          # 0.0 (실제 영상) ~ 1.0 (AI 생성)
    reason: str           # 판단 근거 (백엔드 description에 활용)
    regions: list[dict] = field(default_factory=list)
    # regions 예시: [{"x":120,"y":80,"width":50,"height":50,"issue":"Pixel Artifact"}]


# ─────────────────────────────────────────────────────────────────────────────
# 추상 기반 클래스
# ─────────────────────────────────────────────────────────────────────────────

class BaseAnalyzer(ABC):
    """
    새 분석기 추가 시 이 클래스를 상속하고 analyze()만 구현하면 됩니다.
    setup()은 무거운 모델 로드가 있을 때만 오버라이드하세요.
    """

    name: str

    def setup(self) -> bool:
        """서버 시작 시 한 번만 호출. 모델 로드 등 초기화."""
        try:
            self._setup()
            return True
        except Exception as e:
            print(f"[{self.name}] setup 실패: {e}")
            return False

    def _setup(self):
        """서브클래스에서 필요할 때만 오버라이드"""
        pass

    @abstractmethod
    def analyze(self, frames: list[np.ndarray]) -> AnalyzerResult:
        """
        Args:
            frames: OpenCV BGR 이미지 배열 리스트 (shape: H x W x 3)
        Returns:
            AnalyzerResult(score=0~1, reason="...", regions=[...])
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLIP 분석기 (핵심)
# ─────────────────────────────────────────────────────────────────────────────

class CLIPAnalyzer(BaseAnalyzer):
    """
    CLIP Zero-shot으로 "AI 생성 영상" vs "실제 영상" 확률을 계산합니다.

    원리:
      CLIP은 이미지와 텍스트를 같은 임베딩 공간에 매핑합니다.
      각 프레임이 AI 생성 텍스트 묘사에 얼마나 가까운지 측정합니다.

    v3 업그레이드 경로:
      이 클래스를 EfficientNet fine-tune 버전으로 교체하면 됩니다.
      인터페이스(analyze)가 동일하므로 inference.py는 수정 불필요.
    """
    name = "clip"

    def _setup(self):
        import open_clip
        import torch

        self.device = CLIP_CONFIG["device"]
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            CLIP_CONFIG["model_name"],
            pretrained=CLIP_CONFIG["pretrained"],
            device=self.device,
        )
        self.tokenizer = open_clip.get_tokenizer(CLIP_CONFIG["model_name"])
        self.model.eval()

        # 텍스트 임베딩 미리 계산 (추론 시 빠르게)
        self._ai_feats   = self._encode_texts(CLIP_CONFIG["ai_prompts"])
        self._real_feats = self._encode_texts(CLIP_CONFIG["real_prompts"])
        print(f"[CLIPAnalyzer] 준비 완료 (device={self.device})")

    def _encode_texts(self, texts: list[str]):
        import torch
        tokens = self.tokenizer(texts).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats

    def _encode_frame(self, frame: np.ndarray):
        """BGR numpy 프레임 → CLIP 이미지 특징 벡터"""
        import torch
        from PIL import Image
        rgb = frame[:, :, ::-1]
        pil = Image.fromarray(rgb.astype(np.uint8))
        tensor = self.preprocess(pil).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_image(tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats

    def analyze(self, frames: list[np.ndarray]) -> AnalyzerResult:
        import torch
        if not frames:
            return AnalyzerResult(score=0.5, reason="분석 프레임 없음")

        frame_scores = []
        for frame in frames:
            img_feats = self._encode_frame(frame)
            ai_sim   = (img_feats @ self._ai_feats.T).mean().item()
            real_sim = (img_feats @ self._real_feats.T).mean().item()
            logits   = torch.tensor([ai_sim, real_sim]) * 100
            probs    = torch.softmax(logits, dim=0)
            frame_scores.append(probs[0].item())

        score = float(np.mean(frame_scores))
        return AnalyzerResult(
            score=score,
            reason=f"CLIP 분석 AI 유사도: {score:.1%} (프레임 {len(frames)}개 평균)",
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. 주파수 분석기
# ─────────────────────────────────────────────────────────────────────────────

class FrequencyAnalyzer(BaseAnalyzer):
    """
    FFT(고속 푸리에 변환)로 AI 영상 특유의 주파수 아티팩트를 감지합니다.

    원리:
      AI 생성 영상은 업샘플링 과정에서 주파수 도메인에 규칙적인
      격자 패턴이 생깁니다. 이를 고주파 에너지 비율과 방사형 분산으로 측정합니다.

    참고: "Leveraging Frequency Analysis for Deep Fake Image Recognition"
          (Frank et al., ICML 2020)
    """
    name = "frequency"

    def _setup(self):
        print("[FrequencyAnalyzer] 준비 완료 (numpy FFT)")

    def _analyze_single_frame(self, frame: np.ndarray) -> tuple[float, list[dict]]:
        """
        Returns:
            (score 0~1, detected_regions 리스트)
        """
        gray = np.mean(frame, axis=2)
        fft  = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        mag = np.log1p(np.abs(fft_shift))

        h, w = mag.shape
        cx, cy = w // 2, h // 2

        # 고주파 에너지 비율
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
        r    = min(h, w) // 4
        lo   = mag[dist <= r].sum()
        hi   = mag[dist >  r].sum()
        hi_ratio = hi / (lo + hi + 1e-8)

        # 방사형 평균 분산 (아티팩트 있으면 피크가 생김)
        radial = [
            mag[(dist >= r_i - 0.5) & (dist < r_i + 0.5)].mean()
            for r_i in range(1, min(cx, cy))
            if (dist >= r_i - 0.5).any()
        ]
        rad_var = float(np.var(radial) / (np.mean(radial) + 1e-8)) if radial else 0.0

        # 방향성 비대칭
        h_e = mag[cy-2:cy+2, :].sum()
        v_e = mag[:, cx-2:cx+2].sum()
        asym = abs(h_e - v_e) / (h_e + v_e + 1e-8)

        thr = FREQUENCY_CONFIG["high_freq_threshold"]
        score_hi  = max(0.0, 1.0 - abs(hi_ratio - thr) / thr)
        score_rad = min(1.0, rad_var / 5.0)
        score_asy = min(1.0, float(asym) * 3.0)
        score = score_hi * 0.4 + score_rad * 0.4 + score_asy * 0.2

        # 이상 점수가 높은 프레임 영역을 region으로 표시
        regions = []
        if score > 0.6:
            # 고주파 에너지가 몰린 영역 추정 (단순화: 전체 프레임)
            regions.append({
                "x": 0, "y": 0,
                "width": frame.shape[1], "height": frame.shape[0],
                "issue": f"Frequency Artifact (score={score:.2f})",
            })

        return float(score), regions

    def analyze(self, frames: list[np.ndarray]) -> AnalyzerResult:
        if not frames:
            return AnalyzerResult(score=0.5, reason="분석 프레임 없음")

        all_scores, all_regions = [], []
        for frame in frames:
            s, r = self._analyze_single_frame(frame)
            all_scores.append(s)
            all_regions.extend(r)

        score = float(np.mean(all_scores))
        return AnalyzerResult(
            score=score,
            reason=f"FFT 주파수 아티팩트 점수: {score:.3f}",
            regions=all_regions,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. 메타데이터 분석기
# ─────────────────────────────────────────────────────────────────────────────

class MetadataAnalyzer(BaseAnalyzer):
    """
    영상 메타데이터에서 AI 생성 흔적을 감지합니다.

    감지 항목:
      - 인코더 태그에 AI 툴 이름 포함 여부 (runway, sora, pika 등)
      - C2PA (AI 생성 콘텐츠 인증 표준) 마커
      - AI 도구 전형 해상도 (512x512, 768x512 등)

    주의: 메타데이터는 쉽게 제거/변조 가능하므로 보조 신호로만 활용합니다.
    ffprobe(ffmpeg)가 없으면 자동으로 건너뜁니다.
    """
    name = "metadata"

    def _setup(self):
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
            self._has_ffprobe = True
            print("[MetadataAnalyzer] ffprobe 사용 가능")
        except Exception:
            self._has_ffprobe = False
            print("[MetadataAnalyzer] ffprobe 없음 - 메타데이터 분석 건너뜀")

    def analyze_path(self, video_path: str) -> AnalyzerResult:
        """
        파일 경로 기반 분석. inference.py에서 직접 호출합니다.
        (frames 기반 analyze()와 별도로 운용)
        """
        if not self._has_ffprobe:
            return AnalyzerResult(score=0.5, reason="ffprobe 없음, 분석 건너뜀")

        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path,
            ]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(out.stdout) if out.returncode == 0 else {}
        except Exception:
            return AnalyzerResult(score=0.5, reason="ffprobe 실행 실패")

        if not data:
            return AnalyzerResult(score=0.5, reason="메타데이터 없음")

        fmt    = data.get("format", {})
        tags   = fmt.get("tags", {})
        streams = data.get("streams", [])

        scores, reasons = [], []

        # 1. 의심 인코더 이름
        encoder_str = " ".join([
            tags.get("encoder", ""),
            tags.get("comment", ""),
            tags.get("description", ""),
        ]).lower()

        found = [k for k in METADATA_CONFIG["suspicious_encoders"] if k in encoder_str]
        if found:
            scores.append(0.95)
            reasons.append(f"AI 인코더 발견: {found}")
        else:
            scores.append(0.2)

        # 2. C2PA 마커
        if any("c2pa" in str(v).lower() for v in tags.values()):
            scores.append(0.90)
            reasons.append("C2PA AI 생성 마커 존재")
        else:
            scores.append(0.2)

        # 3. AI 전형 해상도
        AI_RES = {(512,512),(768,512),(512,768),(1024,576),(576,1024)}
        for s in streams:
            if s.get("codec_type") == "video":
                res = (s.get("width", 0), s.get("height", 0))
                if res in AI_RES:
                    scores.append(0.75)
                    reasons.append(f"AI 전형 해상도: {res[0]}x{res[1]}")
                else:
                    scores.append(0.2)
                break

        score = float(np.mean(scores)) if scores else 0.5
        reason = " | ".join(reasons) if reasons else "메타데이터 이상 징후 없음"
        return AnalyzerResult(score=score, reason=reason)

    def analyze(self, frames: list[np.ndarray]) -> AnalyzerResult:
        # frames만으로는 메타데이터 분석 불가
        # inference.py에서 analyze_path()를 직접 호출합니다
        return AnalyzerResult(score=0.5, reason="파일 경로 필요 (analyze_path 사용)")
