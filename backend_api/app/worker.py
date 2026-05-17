import os
from pathlib import Path
import yt_dlp

from celery import Celery
from ai_engine.src.inference import run_ai_video_analysis
from app.settings import REDIS_URL, UPLOAD_DIR, RESULT_DIR

app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

app.conf.task_track_started = True


def _update_task_state(task, state, status, progress, message, selected_targets=None, selected_analyzers=None):
    task.update_state(
        state=state,
        meta={
            "status": status,
            "progress": progress,
            "message": message,
            "selected_targets": selected_targets or [],
            "selected_analyzers": selected_analyzers or []
        }
    )


def _error_response(error_code, message):
    return {
        "status": "error",
        "error_code": error_code,
        "message": message
    }


def _normalize_analysis_error(result):
    if not isinstance(result, dict):
        return result

    if result.get("status") != "error":
        return result

    if result.get("error_code"):
        return result

    message = result.get("message", "")

    if "파일 없음" in message:
        result["error_code"] = "FILE_NOT_FOUND"

    elif "지원하지 않는 형식" in message:
        result["error_code"] = "UNSUPPORTED_FORMAT"

    elif "너무 짧음" in message:
        result["error_code"] = "VIDEO_TOO_SHORT"

    elif "너무 긺" in message:
        result["error_code"] = "VIDEO_TOO_LONG"

    elif "프레임 추출 실패" in message:
        result["error_code"] = "FRAME_EXTRACTION_FAILED"

    else:
        result["error_code"] = "ANALYSIS_FAILED"

    return result


@app.task(name="start_ai_analysis", bind=True)
def start_ai_analysis(self, video_path, task_id, targets=None):
    try:
        output_dir = f"{RESULT_DIR}/{task_id}"
        os.makedirs(output_dir, exist_ok=True)

        _update_task_state(
            self,
            "VALIDATING",
            "validating",
            5,
            "업로드된 영상 파일을 확인하는 중입니다.",
            targets
        )

        if not os.path.exists(video_path):
            return _error_response(
                "FILE_NOT_FOUND",
                "업로드된 영상 파일을 찾을 수 없습니다."
            )

        def progress_callback(state, status, progress, message, selected_analyzers=None):
            _update_task_state(
                self,
                state,
                status,
                progress,
                message,
                targets,
                selected_analyzers
            )

        result = run_ai_video_analysis(
            video_path,
            output_dir,
            targets,
            progress_callback=progress_callback
        )

        result = _normalize_analysis_error(result)

        if isinstance(result, dict) and targets is not None:
            result["targets"] = targets

        return result

    except Exception as e:
        return _error_response(
            "ANALYSIS_FAILED",
            f"파일 분석 실패: {str(e)}"
        )


@app.task(name="start_url_analysis", bind=True)
def start_url_analysis(self, url, task_id, targets=None):
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(RESULT_DIR, exist_ok=True)

        if not url or not isinstance(url, str):
            return _error_response(
                "INVALID_URL",
                "URL이 비어 있거나 올바르지 않습니다."
            )

        _update_task_state(
            self,
            "DOWNLOADING",
            "downloading",
            5,
            "URL 영상을 다운로드하는 중입니다.",
            targets
        )

        output_template = f"{UPLOAD_DIR}/{task_id}.%(ext)s"

        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_path = ydl.prepare_filename(info)

        except Exception as e:
            return _error_response(
                "DOWNLOAD_FAILED",
                f"영상 다운로드에 실패했습니다. URL을 확인해주세요. 상세 오류: {str(e)}"
            )

        final_path = Path(downloaded_path)

        if final_path.suffix.lower() != ".mp4":
            mp4_path = final_path.with_suffix(".mp4")

            if mp4_path.exists():
                final_path = mp4_path

        if not final_path.exists():
            return _error_response(
                "DOWNLOAD_FILE_NOT_FOUND",
                f"다운로드된 파일을 찾을 수 없습니다: {final_path}"
            )

        output_dir = f"{RESULT_DIR}/{task_id}"
        os.makedirs(output_dir, exist_ok=True)

        _update_task_state(
            self,
            "VALIDATING",
            "validating",
            15,
            "다운로드된 영상 파일을 확인하는 중입니다.",
            targets
        )

        def progress_callback(state, status, progress, message, selected_analyzers=None):
            _update_task_state(
                self,
                state,
                status,
                progress,
                message,
                targets,
                selected_analyzers
            )

        result = run_ai_video_analysis(
            str(final_path),
            output_dir,
            targets,
            progress_callback=progress_callback
        )

        result = _normalize_analysis_error(result)

        if isinstance(result, dict) and targets is not None:
            result["targets"] = targets

        return result

    except Exception as e:
        return _error_response(
            "URL_ANALYSIS_FAILED",
            f"URL 분석 실패: {str(e)}"
        )