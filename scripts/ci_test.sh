#!/usr/bin/env bash
# CI 入口：Jenkins / 本地都可调用
# 用法:
#   bash scripts/ci_test.sh smoke
#   bash scripts/ci_test.sh full
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SUITE="${1:-full}"
BOOTSTRAP_PY="${PYTHON_BOOTSTRAP:-}"
if [[ -z "$BOOTSTRAP_PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PY=python3
  else
    BOOTSTRAP_PY=python
  fi
fi

echo "==> workspace: $ROOT"
echo "==> suite: $SUITE"
echo "==> bootstrap python: $($BOOTSTRAP_PY --version 2>&1)"

# 独立 venv，避免污染 agent 全局环境
if [[ ! -d .venv ]]; then
  echo "==> create venv"
  "$BOOTSTRAP_PY" -m venv .venv
fi

# shellcheck disable=SC1091
if [[ -f .venv/bin/activate ]]; then
  # Linux / macOS agent
  # shellcheck source=/dev/null
  source .venv/bin/activate
  PYTHON=python
elif [[ -f .venv/Scripts/activate ]]; then
  # Git Bash on Windows agent
  # shellcheck source=/dev/null
  source .venv/Scripts/activate
  PYTHON=python
else
  echo "ERROR: venv activate script not found" >&2
  exit 1
fi

echo "==> venv python: $($PYTHON --version 2>&1)"
"$PYTHON" -m pip install -U pip -q
"$PYTHON" -m pip install -r requirements.txt -q
# 后端被测系统依赖（real 环境需要：conftest 的 backend_server fixture 会用子进程起 uvicorn）
if [[ -f apps/backend/requirements.txt ]]; then
  "$PYTHON" -m pip install -r apps/backend/requirements.txt -q
fi

# 清空产物，但保留目录内的 .gitignore
mkdir -p allure-results reports
find allure-results -mindepth 1 ! -name '.gitignore' -exec rm -rf {} + 2>/dev/null || true
find reports -mindepth 1 ! -name '.gitignore' -exec rm -rf {} + 2>/dev/null || true

JUNIT="reports/junit.xml"
COMMON=(
  -v
  --tb=short
  --junitxml="$JUNIT"
  --alluredir=allure-results
)

case "$SUITE" in
  smoke)
    echo "==> pytest smoke"
    "$PYTHON" -m pytest tests/ -m smoke "${COMMON[@]}"
    ;;
  full)
    echo "==> pytest full"
    "$PYTHON" -m pytest tests/ "${COMMON[@]}"
    ;;
  *)
    echo "ERROR: unknown suite '$SUITE' (use smoke|full)" >&2
    exit 2
    ;;
esac

echo "==> done. junit=$JUNIT allure=allure-results/"
