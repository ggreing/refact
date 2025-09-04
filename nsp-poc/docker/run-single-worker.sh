#!/bin/bash

# 단일 워커 실행 스크립트
# Usage: ./run-single-worker.sh [ai_assist|ai_chat|ai_translate]

WORKER_TYPE=${1:-ai_assist}

echo "Starting single worker: $WORKER_TYPE"

case $WORKER_TYPE in
    "ai_assist")
        docker-compose up -d rabbitmq mongo minio qdrant
        echo "Dependencies started, running AI Assist worker..."
        docker-compose up worker-ai-assist
        ;;
    "ai_chat")
        docker-compose up -d rabbitmq mongo minio qdrant
        echo "Dependencies started, running AI Chat worker..."
        docker-compose up worker-ai-chat
        ;;
    *)
        echo "Invalid worker type. Use: ai_assist or ai_chat"
        exit 1
        ;;
esac