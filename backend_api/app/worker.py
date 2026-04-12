import os
from pathlib import Path
import yt_dlp

from celery import Celery
from ai_engine.src.inference import run_ai_video_analysis

app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@app.task(name="start_ai_analysis")
def start_ai_analysis(video_path, task_id):
    output_dir = f"storage/results/{task_id}"
    os.makedirs(output_dir, exist_ok=True)

    result = run_ai_video_analysis(video_path, output_dir)
    return result


@app.task(name="start_url_analysis")
def start_url_analysis(url, task_id):
    try:
        os.makedirs("storage/uploads", exist_ok=True)
        os.makedirs("storage/results", exist_ok=True)

        output_template = f"storage/uploads/{task_id}.%(ext)s"

        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)

        final_path = Path(downloaded_path)
        if final_path.suffix.lower() != ".mp4":
            mp4_path = final_path.with_suffix(".mp4")
            if mp4_path.exists():
                final_path = mp4_path

        if not final_path.exists():
            return {
                "status": "error",
                "message": f"다운로드된 파일을 찾을 수 없습니다: {final_path}"
            }

        output_dir = f"storage/results/{task_id}"
        os.makedirs(output_dir, exist_ok=True)

        result = run_ai_video_analysis(str(final_path), output_dir)
        return result

    except Exception as e:
        return {
            "status": "error",
            "message": f"URL 분석 실패: {str(e)}"
        }