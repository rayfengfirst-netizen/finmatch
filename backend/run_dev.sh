#!/usr/bin/env bash
# 本地开发：默认端口 8770（与常见占用端口错开）。可改环境变量：PORT=8899 ./run_dev.sh
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
PORT="${PORT:-8770}"
exec uvicorn app.main:app --reload --host 127.0.0.1 --port "$PORT"
