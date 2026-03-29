# backend_api/main.py
from fastapi import FastAPI, UploadFile, File
import uuid
import os
from app.worker import start_ai_analysis

app = FastAPI()

@app.post("/api/v1/analyze")
async def create_upload_file(file: UploadFile = File(...)):
    # 1. 고유 ID 생성 (접수번호)
    task_id = str(uuid.uuid4())
    
    # 2. 영상 파일 임시 저장
    video_path = f"storage/uploads/{task_id}_{file.filename}"
    os.makedirs("storage/uploads", exist_ok=True)
    with open(video_path, "wb") as buffer:
        buffer.write(await file.read())

    # 3. [핵심] AI 담당자에게 일 시키기 (비동기 호출)
    # 서버는 이 줄에서 안 기다리고 바로 다음으로 넘어갑니다!
    task = start_ai_analysis.delay(video_path, task_id)

    # 4. 프론트엔드에게 접수번호 알려주기 
    return {"task_id": task_id, "status": "processing"}