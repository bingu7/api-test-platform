#!/usr/bin/env bash
# 前台启动后端被测系统（调试用；按 Ctrl+C 退出）
# 用法: bash scripts/start_backend.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
elif [[ -f .venv/Scripts/activate ]]; then
  source .venv/Scripts/activate
fi

echo "==> 启动 FastAPI 后端: http://127.0.0.1:8000"
echo "==> Swagger UI:        http://127.0.0.1:8000/docs"
echo "==> OpenAPI 规范:       http://127.0.0.1:8000/openapi.json"
echo "==> 按 Ctrl+C 退出"
python -m uvicorn apps.backend.main:app --reload --port 8000
