#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
PYTHON="$PROJECT_DIR/.venv-server/bin/python"
CONFIG="$PROJECT_DIR/.runtime/supervisord.conf"
case "${1:-status}" in
    start)
        if [[ ! -f .env ]]; then
            echo '请先配置 .env 中的本地模型路径、adapter、端口及访问口令。' >&2
            exit 1
        fi
        mkdir -p logs .runtime
        if [[ ! -f "$CONFIG" ]]; then
            if [[ "$PROJECT_DIR" != /root/autodl-tmp/shellguard-ai ]]; then
                echo '请根据实际项目路径修改 deploy/autodl-supervisord.conf 后复制到 .runtime/supervisord.conf。' >&2
                exit 1
            fi
            cp deploy/autodl-supervisord.conf "$CONFIG"
        fi
        if "$PYTHON" -m supervisor.supervisorctl -c "$CONFIG" pid >/dev/null 2>&1; then
            if "$PYTHON" -m supervisor.supervisorctl -c "$CONFIG" status shellguard | grep -q RUNNING; then
                echo 'shellguard 已运行'
            else
                "$PYTHON" -m supervisor.supervisorctl -c "$CONFIG" start shellguard
            fi
        else
            "$PYTHON" -m supervisor.supervisord -c "$CONFIG"
        fi
        ;;
    stop|restart|status)
        "$PYTHON" -m supervisor.supervisorctl -c "$CONFIG" "${1:-status}" shellguard
        ;;
    logs)
        tail -n 80 logs/web.log
        ;;
    *)
        echo '用法：bash scripts/autodl_service.sh {start|stop|restart|status|logs}' >&2
        exit 2
        ;;
esac
