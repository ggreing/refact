#!/bin/bash

# NSP Chat Workers 실행 스크립트

echo "Starting NSP Chat Workers..."

# 전체 스택 실행
docker-compose up -d

echo "Services started:"
echo "- RabbitMQ: http://localhost:15672 (guest/guest)"
echo "- API: http://localhost:8000"
echo "- Mongo Express: http://localhost:8081"
echo "- MinIO Console: http://localhost:9001"
echo "- Qdrant: http://localhost:6333"

echo ""
echo "Workers running:"
echo "- AI Assist Worker (nsp-worker-ai-assist)"
echo "- AI Chat Worker (nsp-worker-ai-chat)"

echo ""
echo "To check worker logs:"
echo "docker-compose logs -f worker-ai-assist"
echo "docker-compose logs -f worker-ai-chat"

echo ""
echo "To stop all services:"
echo "docker-compose down"