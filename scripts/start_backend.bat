@echo off
REM Start the FastAPI backend (foreground; press Ctrl+C to stop)
REM Usage: scripts\start_backend.bat
setlocal EnableExtensions
cd /d "%~dp0\.."

REM Prefer .venv ONLY if it actually has uvicorn; otherwise fall back to system python.
REM (A half-installed .venv must not break startup.)
set PY=python
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import uvicorn" >nul 2>nul
  if not errorlevel 1 set PY=.venv\Scripts\python.exe
)

echo ==^> python: %PY%
echo ==^> FastAPI backend: http://127.0.0.1:8000
echo ==^> Swagger UI:      http://127.0.0.1:8000/docs
echo ==^> OpenAPI spec:    http://127.0.0.1:8000/openapi.json
echo ==^> Press Ctrl+C to stop
"%PY%" -m uvicorn apps.backend.main:app --reload --port 8000
