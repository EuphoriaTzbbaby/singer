#!/usr/bin/env bash
# 启动本地 Web 服务（默认 http://127.0.0.1:8765）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/uvicorn ]; then
  echo "环境不存在，请先运行 scripts/setup.sh" >&2
  exit 1
fi

HOST="${SINGER_HOST:-127.0.0.1}"
PORT="${SINGER_PORT:-8765}"

exec .venv/bin/uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --reload \
  --reload-dir app
