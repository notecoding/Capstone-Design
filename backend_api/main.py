from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from celery.result import AsyncResult
import uuid
import os
import json
import redis

from app.worker import start_ai_analysis, app as celery_app
from app.api.analysis import router as analysis_router
from app.settings import (
    REDIS_URL,
    CORS_ORIGINS,
    STORAGE_DIR,
    UPLOAD_DIR,
    RESULT_DIR,
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
)

app = FastAPI(
    title="AI Video Detection Backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

app.include_router(analysis_router)


@app.get("/")
def root():
    return {
        "status": "running",
        "message": "AI Video Detection Backend is running."
    }


@app.get("/api/v1/health")
def health_check():
    redis_status = "disconnected"

    try:
        redis_client = redis.Redis.from_url(REDIS_URL)
        redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    storage_status = {
        "storage_dir": os.path.exists(STORAGE_DIR),
        "upload_dir": os.path.exists(UPLOAD_DIR),
        "result_dir": os.path.exists(RESULT_DIR),
    }

    all_storage_ready = all(storage_status.values())
    server_status = "ok" if redis_status == "connected" and all_storage_ready else "warning"

    return {
        "status": server_status,
        "api": "running",
        "redis": redis_status,
        "storage": storage_status,
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB
    }


@app.post("/api/v1/analyze")
async def create_upload_file(
    file: UploadFile = File(...),
    targets: str = Form("[]")
):
    task_id = str(uuid.uuid4())

    try:
        parsed_targets = json.loads(targets)

        if not isinstance(parsed_targets, list):
            parsed_targets = []

    except Exception:
        parsed_targets = []

    file_content = await file.read()

    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="업로드 가능한 파일 크기를 초과했습니다."
        )

    video_path = f"{UPLOAD_DIR}/{task_id}_{file.filename}"

    with open(video_path, "wb") as buffer:
        buffer.write(file_content)

    task = start_ai_analysis.apply_async(
        args=[video_path, task_id, parsed_targets],
        task_id=task_id
    )

    return {
        "task_id": task.id,
        "status": "queued",
        "progress": 0,
        "message": "분석 작업이 대기열에 등록되었습니다."
    }


@app.get("/api/v1/result/{task_id}")
def get_analysis_result(task_id: str):
    task = AsyncResult(task_id, app=celery_app)
    state = task.state
    info = task.info if isinstance(task.info, dict) else {}

    if state == "PENDING":
        return {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "아직 작업이 시작되지 않았습니다."
        }

    if state in [
        "STARTED",
        "DOWNLOADING",
        "VALIDATING",
        "EXTRACTING_FRAMES",
        "EXTRACTING_TEMPORAL",
        "ANALYZING_CLIP",
        "ANALYZING_FREQUENCY",
        "ANALYZING_METADATA",
        "ANALYZING_TEMPORAL",
        "SAVING_EVIDENCE",
        "BUILDING_RESULT",
    ]:
        return {
            "task_id": task_id,
            "status": info.get("status", state.lower()),
            "progress": info.get("progress", 0),
            "message": info.get("message", "AI 분석이 진행 중입니다."),
            "selected_targets": info.get("selected_targets", []),
            "selected_analyzers": info.get("selected_analyzers", [])
        }

    if state == "SUCCESS":
        result = task.result

        if isinstance(result, dict) and result.get("status") == "error":
            return {
                "task_id": task_id,
                "status": "failed",
                "progress": 100,
                "error_code": result.get("error_code", "ANALYSIS_FAILED"),
                "message": result.get("message", "분석 중 오류가 발생했습니다."),
                "result": None
            }

        return {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "message": "AI 분석이 완료되었습니다.",
            "result": result
        }

    if state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "progress": info.get("progress", 0),
            "error_code": info.get("error_code", "WORKER_FAILED"),
            "message": str(task.result),
            "result": None
        }

    return {
        "task_id": task_id,
        "status": state.lower(),
        "progress": info.get("progress", 0),
        "message": info.get("message", "알 수 없는 상태입니다."),
        "result": None
    }