from pathlib import Path
from uuid import uuid4
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent.parent
VIDEO_DIR = BASE_DIR / "uploads" / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

def download_video_from_url(url: str) -> str:
    file_id = uuid4().hex
    output_template = str(VIDEO_DIR / f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_path = ydl.prepare_filename(info)

    final_path = Path(downloaded_path)
    if final_path.suffix.lower() != ".mp4":
        mp4_path = final_path.with_suffix(".mp4")
        if mp4_path.exists():
            final_path = mp4_path

    return str(final_path)