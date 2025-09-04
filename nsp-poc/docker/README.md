# Docker 배포 가이드

Base Chat API를 Docker로 실행하는 방법입니다.

## 🚀 빠른 시작

### 1. 환경 설정
```bash
cd docker/
cp .env.example .env
```

### 2. 도커 컴포즈 실행
```bash
# 백그라운드 실행
docker-compose up -d

# 로그 확인하면서 실행
docker-compose up
```

### 3. 서비스 확인
- **API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **RabbitMQ 관리UI**: http://localhost:15672 (guest/guest)

## 📋 서비스 구성

### API 서비스
- **포트**: 8000
- **헬스체크**: `/health`
- **포함 내용**: api/ + shared/ 폴더

### RabbitMQ 서비스
- **AMQP 포트**: 5672
- **관리 UI**: 15672
- **기본 계정**: guest/guest

## 🛠️ 개발 모드

개발 중에는 볼륨 마운트로 코드 변경사항이 반영됩니다:

```bash
# 볼륨 마운트 활성화 상태로 실행
docker-compose up -d

# API 재시작
docker-compose restart api
```

## 📝 로그 확인

```bash
# 모든 서비스 로그
docker-compose logs -f

# API만 로그 확인
docker-compose logs -f api

# RabbitMQ 로그 확인
docker-compose logs -f rabbitmq
```

## 🔧 트러블슈팅

### RabbitMQ 연결 실패
```bash
# RabbitMQ 상태 확인
docker-compose ps rabbitmq

# RabbitMQ 재시작
docker-compose restart rabbitmq
```

### API 헬스체크 실패
```bash
# API 컨테이너 상태 확인
docker-compose ps api

# API 로그 확인
docker-compose logs api

# API 재빌드
docker-compose build api
```

## 🧹 정리

```bash
# 서비스 중지
docker-compose down

# 볼륨까지 삭제
docker-compose down -v

# 이미지까지 삭제
docker-compose down --rmi all -v
```

## 📊 모니터링

### 컨테이너 상태 확인
```bash
docker-compose ps
```

### 리소스 사용량 확인
```bash
docker-compose top
```

### RabbitMQ 큐 상태 확인
RabbitMQ 관리 UI (http://localhost:15672)에서 확인:
- `base_chat.messages` Exchange
- `base_chat.responses` Exchange  
- `q.base_chat.messages` Queue