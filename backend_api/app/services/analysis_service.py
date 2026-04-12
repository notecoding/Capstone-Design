from pathlib import Path
from uuid import uuid4
from ai_engine.src.inference import run_ai_video_analysis

BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_DIR = BASE_DIR / "uploads" / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

def analyze_video_file(video_path: str) -> dict:
    job_id = uuid4().hex
    output_dir = RESULT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_ai_video_analysis(video_path=video_path, output_dir=str(output_dir))
    return result