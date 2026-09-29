# 常用命令（Git Bash / WSL / Linux Agent 有 make 时可用）
# Windows 无 make 时请用 scripts\ci_test.bat 或 README 中的 pytest 命令

.PHONY: help install install-backend smoke full ci-smoke ci-full clean report backend backend-stop

help:
	@echo "make install        - pip install -r requirements.txt"
	@echo "make install-backend - 装后端被测系统依赖 (apps/backend)"
	@echo "make smoke          - pytest -m smoke"
	@echo "make full           - pytest 全量（dev=Mock）"
	@echo "make smoke-real     - TEST_ENV=real pytest -m smoke（FastAPI后端）"
	@echo "make full-real      - TEST_ENV=real pytest 全量（FastAPI后端）"
	@echo "make backend        - 前台启动 FastAPI 后端 (热调试用)"
	@echo "make ci-smoke       - 与 Jenkins 相同的 smoke 入口"
	@echo "make ci-full        - 与 Jenkins 相同的 full 入口"
	@echo "make report         - allure serve allure-results"
	@echo "make clean          - 清理报告与缓存"

install:
	python -m pip install -U pip
	python -m pip install -r requirements.txt

install-backend:
	python -m pip install -r apps/backend/requirements.txt

smoke:
	python -m pytest tests/ -v -m smoke --tb=short

full:
	python -m pytest tests/ -v --tb=short

smoke-real:
	TEST_ENV=real python -m pytest tests/ -v -m smoke --tb=short

full-real:
	TEST_ENV=real python -m pytest tests/ -v --tb=short

backend:
	python -m uvicorn apps.backend.main:app --reload --port 8000

ci-smoke:
	bash scripts/ci_test.sh smoke

ci-full:
	bash scripts/ci_test.sh full

report:
	allure serve allure-results

clean:
	rm -rf allure-results/* reports/* .pytest_cache __pycache__
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
