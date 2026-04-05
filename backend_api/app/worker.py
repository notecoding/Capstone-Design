# app/worker.py

from celery import Celery
import os
from ai_engine.src.inference import run_ai_video_analysis 

# 핵심: 'localhost' 대신 '127.0.0.1' 숫자를 직접 씁니다.
app = Celery('my_tasks', 
             broker='redis://127.0.0.1:6379/0', 
             backend='redis://127.0.0.1:6379/0')

@app.task
def start_ai_analysis(video_path, task_id):
    output_dir = f"storage/results/{task_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    result = run_ai_video_analysis(video_path, output_dir)
    return result
