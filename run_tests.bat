@echo off
setlocal
cd /d %~dp0

if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=python
)

echo === Install deps ===
"%PY%" -m pip install -r requirements.txt -q

echo === CI-compatible full run ===
call scripts\ci_test.bat full
set ERR=%ERRORLEVEL%

echo === Done (exit %ERR%) ===
pause
exit /b %ERR%
