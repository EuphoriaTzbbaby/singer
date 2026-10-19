#!/usr/bin/env bash
# 创建/更新本地环境（Python 3.11 + 音频依赖）
set -euo pipefail
cd "$(dirname "$0")/.."

export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"

command -v uv >/dev/null 2>&1 || {
  echo "未找到 uv，请先安装：brew install uv" >&2
  exit 1
}

uv python install 3.11
uv sync --extra audio
echo
echo "环境就绪。启动：scripts/dev.sh"
