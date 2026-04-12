from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

from app.worker import start_url_analysis

router = APIRouter()

class UrlRequest(BaseModel):
    url: str

@router.post("/api/v1/analyze/url")
def analyze_video_url(request: UrlRequest):
    try:
        task_id = str(uuid.uuid4())

        task = start_url_analysis.apply_async(
            args=[request.url, task_id],
            task_id=task_id
        )

        return {
            "task_id": task.id,
            "status": "processing",
            "message": "URL 영상 다운로드 및 AI 분석이 시작되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))