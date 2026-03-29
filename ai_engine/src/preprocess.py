import cv2
import torch
from torchvision import transforms
from PIL import Image

def get_frame_tensor(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, None
        
    # 영상의 중간 프레임 추출
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    middle_idx = total_frames // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_idx)
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret: 
        return None, None

    # 원본 복사본 (나중에 박스 그릴 용도)
    raw_img = frame.copy()

    # AI 모델용 전처리
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(frame_rgb)
    
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    return transform(img_pil).unsqueeze(0), raw_img