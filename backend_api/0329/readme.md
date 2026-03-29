🎥 AI 딥페이크 탐지 시스템 백엔드 구축 리포트

1. 현재까지 완료된 진행 상황

현재 백엔드 서버는 **"영상을 받아서 AI에게 넘기고, 분석 결과를 받아오는 전 과정"**이 자동화되어 있습니다.

API 서버 구축 (FastAPI): 사용자가 영상을 업로드할 수 있는 창구(POST /api/v1/analyze)와 결과를 확인하는 창구(GET /api/v1/analyze/result/{id})를 완성했습니다.

비동기 작업 시스템 (Celery): 영상 분석은 시간이 오래 걸리기 때문에, 서버가 멈추지 않도록 '일꾼(Worker)'에게 일을 맡기는 시스템을 구축했습니다.

메시지 브로커 연결 (Redis): 서버와 일꾼이 서로 소통할 수 있는 '게시판' 역할을 하는 Redis 서버를 연결했습니다.

AI 엔진 통합 (Torch): 실제 딥러닝 모델(EfficientNet)을 불러와 영상을 분석하고 증거 이미지(evidence.jpg)를 생성하는 기능을 연동했습니다.

정적 파일 서빙: AI가 만든 결과 이미지를 웹 브라우저에서 바로 볼 수 있도록 주소(http://127.0.0.1:8000/static/...)를 설정했습니다.

2. 발생했던 주요 오류와 해결 방법

개발 과정에서 만난 에러들은 실제 현업 개발자들도 자주 겪는 '살아있는 공부'였습니다.

에러 메시지 (증상)

원인

해결 방법

ModuleNotFoundError: No module named 'torch'

가상환경(venv)에 AI 분석에 필요한 딥러닝 라이브러리가 설치되지 않음.

pip install torch torchvision 등을 통해 필요한 패키지를 가상환경에 설치함.

.\venv\Scripts\activate : 인식되지 않음

터미널의 현재 위치가 backend_api 폴더인데, 가상환경 폴더는 상위 폴더에 있어서 경로를 못 찾음.

cd ..으로 나가서 켜거나, ..\venv\Scripts\activate처럼 상대 경로를 사용하여 해결함.

Error 11001: No address found (localhost)

윈도우 네트워크 설정 문제로 localhost라는 글자를 컴퓨터가 자기 자신으로 인식하지 못함.

주소를 글자(localhost) 대신 숫자 IP(127.0.0.1)로 직접 수정하여 해결함.

AttributeError: 'NoneType' object has no attribute 'Redis'

파이썬이 Redis와 대화할 때 필요한 통신 도구(라이브러리)가 부족함.

pip install redis를 설치하여 Celery가 Redis와 대화할 수 있게 함.

Cannot connect to redis://... (Connection Error)

메시지 브로커인 Redis 프로그램 자체가 실행되지 않아 일꾼이 일감을 받을 곳이 없음.

redis-server.exe를 실행하여 배경에서 Redis 서비스가 돌아가도록 조치함.

2 RLock(s) were not greened...

윈도우 특성상 Celery가 비동기 작업을 처리하는 방식(Eventlet)과 충돌이 날 뻔함.

pip install eventlet 설치 후 실행 명령어 뒤에 -P eventlet 옵션을 붙여 윈도우 최적화 실행을 함.

3. 실행을 위해 필요한 3가지 '창' (Checklist)

앞으로 테스트를 할 때마다 항상 이 3가지가 켜져 있어야 합니다.

Redis 서버: 데이터 전달 게시판 (redis-server.exe)

API 서버: 사용자 응대 창구 (python -m uvicorn main:app --reload)

AI 일꾼: 실제 영상 분석 수행 (celery -A app.worker worker --loglevel=info -P eventlet)

4. 최종 결과물 확인 경로

API 문서 주소: http://127.0.0.1:8000/docs

영상 업로드 저장소: backend_api/storage/uploads/

AI 분석 결과 저장소: backend_api/storage/results/{task_id}/
