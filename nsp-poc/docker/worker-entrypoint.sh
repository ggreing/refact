#!/bin/bash

# 로그 디렉토리 생성
mkdir -p /app/logs

# PM2 설정 파일에서 instances 개수를 환경변수로 업데이트
if [ -n "$PM2_INSTANCES" ]; then
    # PM2 설정 파일의 instances 값을 환경변수로 치환
    if [ "$WORKER_TYPE" = "ai_assist" ]; then
        CONFIG_FILE="/app/pm2.ai-assist.json"
    elif [ "$WORKER_TYPE" = "ai_chat" ]; then
        CONFIG_FILE="/app/pm2.ai-chat.json"
    else
        CONFIG_FILE="/app/pm2.ecosystem.json"
    fi
    
    # instances 값을 환경변수로 치환
    if [ -f "$CONFIG_FILE" ]; then
        sed -i "s/\"instances\": [0-9]*/\"instances\": $PM2_INSTANCES/" "$CONFIG_FILE"
        echo "Updated PM2 instances to $PM2_INSTANCES in $CONFIG_FILE"
    fi
fi

# 전달받은 명령어 실행
exec "$@"