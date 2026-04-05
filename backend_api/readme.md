# Capstone-Design
Ai파트 수정사항 <br />
init.py 파일내  <br />
from ai_engine.src.inference import run_ai_video_analysis<- 경로 수정 <br />
preprocess.py <br />
from ai_engine.src.config import VIDEO_CONFIG <br />
inference <br />
from ai_engine.src.config import ( <br />
    ANALYZER_WEIGHTS, AI_THRESHOLD, RISK_THRESHOLDS, <br />
    CLIP_CONFIG, FREQUENCY_CONFIG, METADATA_CONFIG, VIDEO_CONFIG, <br />
)
from ai_engine.src.preprocess import extract_frames, save_evidence_frames <br />
프론트엔드 파트 수정사항 <br />
ResultPage.jsx<- 전체적 수정 <br />


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