#!/bin/bash

# PM2 Worker 제어 스크립트
# Usage: ./pm2-control.sh [start|stop|restart|status|logs] [worker_type] [instances]

COMMAND=${1:-status}
WORKER_TYPE=${2:-all}
INSTANCES=${3:-}

get_container_name() {
    case $1 in
        "ai_assist"|"assist")
            echo "nsp-worker-ai-assist"
            ;;
        "ai_chat"|"chat") 
            echo "nsp-worker-ai-chat"
            ;;
        *)
            echo ""
            ;;
    esac
}

execute_pm2_command() {
    local container=$1
    local cmd=$2
    
    if [ -z "$container" ]; then
        echo "Invalid worker type"
        return 1
    fi
    
    echo "Executing: docker exec $container $cmd"
    docker exec "$container" $cmd
}

case $COMMAND in
    "start")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "Starting all workers with PM2..."
            docker-compose up -d worker-ai-assist worker-ai-chat worker-ai-translate
        else
            container=$(get_container_name "$WORKER_TYPE")
            if [ -n "$container" ]; then
                echo "Starting $WORKER_TYPE worker..."
                docker-compose up -d "worker-$WORKER_TYPE"
            fi
        fi
        ;;
    
    "stop")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "Stopping all workers..."
            docker exec nsp-worker-ai-assist pm2 stop all 2>/dev/null || true
            docker exec nsp-worker-ai-chat pm2 stop all 2>/dev/null || true
        else
            container=$(get_container_name "$WORKER_TYPE")
            execute_pm2_command "$container" "pm2 stop all"
        fi
        ;;
    
    "restart")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "Restarting all workers..."
            docker exec nsp-worker-ai-assist pm2 restart all 2>/dev/null || true
            docker exec nsp-worker-ai-chat pm2 restart all 2>/dev/null || true
        else
            container=$(get_container_name "$WORKER_TYPE")
            execute_pm2_command "$container" "pm2 restart all"
        fi
        ;;
    
    "status")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "=== AI Assist Worker Status ==="
            docker exec nsp-worker-ai-assist pm2 list 2>/dev/null || echo "Container not running"
            echo ""
            echo "=== AI Chat Worker Status ==="
            docker exec nsp-worker-ai-chat pm2 list 2>/dev/null || echo "Container not running"
        else
            container=$(get_container_name "$WORKER_TYPE")
            echo "=== $WORKER_TYPE Worker Status ==="
            execute_pm2_command "$container" "pm2 list"
        fi
        ;;
    
    "logs")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "Use specific worker type for logs: assist, chat"
        else
            container=$(get_container_name "$WORKER_TYPE")
            execute_pm2_command "$container" "pm2 logs"
        fi
        ;;
    
    "scale")
        if [ -z "$INSTANCES" ]; then
            echo "Usage: $0 scale [worker_type] [instances]"
            exit 1
        fi
        
        container=$(get_container_name "$WORKER_TYPE")
        if [ -n "$container" ]; then
            echo "Scaling $WORKER_TYPE to $INSTANCES instances..."
            execute_pm2_command "$container" "pm2 scale all $INSTANCES"
        fi
        ;;
    
    "monit")
        if [ "$WORKER_TYPE" = "all" ]; then
            echo "Use specific worker type for monitoring: assist, chat"
        else
            container=$(get_container_name "$WORKER_TYPE")
            execute_pm2_command "$container" "pm2 monit"
        fi
        ;;
    
    *)
        echo "Usage: $0 [start|stop|restart|status|logs|scale|monit] [worker_type] [instances]"
        echo ""
        echo "Commands:"
        echo "  start   - Start workers"
        echo "  stop    - Stop workers" 
        echo "  restart - Restart workers"
        echo "  status  - Show worker status"
        echo "  logs    - Show worker logs"
        echo "  scale   - Scale worker instances"
        echo "  monit   - Show PM2 monitoring"
        echo ""
        echo "Worker types: all, assist, chat"
        exit 1
        ;;
esac