# Worker Dockerfile
FROM node:18-slim as node_base

# Python과 Node.js를 모두 포함한 멀티 단계 빌드
FROM python:3.12-slim

# Node.js 설치 (PM2를 위해)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# PM2 글로벌 설치
RUN npm install -g pm2

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 복사 및 설치 (Worker 전용 requirements.txt 사용)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY shared/ /app/shared/
COPY worker/ /app/worker/

# PM2 설정 파일들 복사
COPY docker/pm2.ecosystem.json /app/pm2.ecosystem.json
COPY docker/pm2.ai-assist.json /app/pm2.ai-assist.json
COPY docker/pm2.ai-chat.json /app/pm2.ai-chat.json

# Entrypoint 스크립트 복사
COPY docker/worker-entrypoint.sh /app/worker-entrypoint.sh
RUN sed -i 's/\r$//' /app/worker-entrypoint.sh
RUN chmod +x /app/worker-entrypoint.sh

# Python 경로 설정
ENV PYTHONPATH="/app"

# PM2 환경 변수
ENV PM2_HOME="/app/.pm2"

# 헬스체크 (PM2 프로세스 확인)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD pm2 jlist | grep -q "online" || exit 1

# Entrypoint 설정
ENTRYPOINT ["/app/worker-entrypoint.sh"]

# PM2로 워커 실행 (기본값, 환경변수로 오버라이드 가능)
CMD ["pm2-runtime", "start", "/app/pm2.ecosystem.json"]