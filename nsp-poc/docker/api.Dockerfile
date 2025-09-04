# Base Chat API Dockerfile
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
# API와 shared 라이브러리 모두 복사
COPY api/ /app/api/
COPY shared/ /app/shared/
COPY fullchain.crt /app/fullchain.crt
COPY private.key /app/private.key

# Python 경로 설정
ENV PYTHONPATH="/app"

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["python", "-m", "api.main"]