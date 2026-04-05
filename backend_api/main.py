from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
from celery.result import AsyncResult
from app.worker import start_ai_analysis, app as celery_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/analyze")
async def create_upload_file(file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())

    video_path = f"storage/uploads/{task_id}_{file.filename}"
    os.makedirs("storage/uploads", exist_ok=True)

    with open(video_path, "wb") as buffer:
        buffer.write(await file.read())

    task = start_ai_analysis.delay(video_path, task_id)

    return {"task_id": task.id, "status": "processing"}


@app.get("/api/v1/result/{task_id}")
def get_analysis_result(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "아직 작업이 시작되지 않았습니다."
        }

    if task.state == "STARTED":
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "AI 분석이 진행 중입니다."
        }

    if task.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task.result
        }

    if task.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "message": str(task.result)
        }

    return {
        "task_id": task_id,
        "status": task.state.lower(),
        "message": "알 수 없는 상태입니다."
    }