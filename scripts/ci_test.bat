@echo off
REM Windows Agent / 本机模拟 CI
REM 用法: scripts\ci_test.bat smoke
REM       scripts\ci_test.bat full
setlocal EnableExtensions
cd /d "%~dp0\.."

set SUITE=%~1
if "%SUITE%"=="" set SUITE=full

if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  where python >nul 2>nul && set PY=python || set PY=py -3
  echo ==^> create venv
  %PY% -m venv .venv
  set PY=.venv\Scripts\python.exe
)

echo ==^> workspace: %CD%
echo ==^> suite: %SUITE%
"%PY%" --version

echo ==^> install deps
"%PY%" -m pip install -U pip -q
"%PY%" -m pip install -r requirements.txt -q

if not exist allure-results mkdir allure-results
if not exist reports mkdir reports
REM 清理旧产物，保留 .gitignore
del /q allure-results\* >nul 2>nul
for /d %%D in (allure-results\*) do rd /s /q "%%D" >nul 2>nul
del /q reports\* >nul 2>nul
for /d %%D in (reports\*) do rd /s /q "%%D" >nul 2>nul

set JUNIT=reports\junit.xml

if /i "%SUITE%"=="smoke" (
  echo ==^> pytest smoke
  "%PY%" -m pytest tests/ -m smoke -v --tb=short --junitxml=%JUNIT% --alluredir=allure-results
  goto :done
)
if /i "%SUITE%"=="full" (
  echo ==^> pytest full
  "%PY%" -m pytest tests/ -v --tb=short --junitxml=%JUNIT% --alluredir=allure-results
  goto :done
)

echo ERROR: unknown suite "%SUITE%" (use smoke^|full)
exit /b 2

:done
echo ==^> done. junit=%JUNIT% allure=allure-results\
exit /b %ERRORLEVEL%
