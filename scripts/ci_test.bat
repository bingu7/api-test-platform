@echo off
REM Windows local CI simulation (mirrors Jenkins / GitHub Actions)
REM Usage: scripts\ci_test.bat smoke
REM        scripts\ci_test.bat full
setlocal EnableExtensions
cd /d "%~dp0\.."

set SUITE=%~1
if "%SUITE%"=="" set SUITE=full

rem A half-installed .venv must not break the run: verify pip works, else recreate.
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m pip --version >nul 2>nul
  if errorlevel 1 (
    echo ==^> existing .venv looks broken ^(no pip^), recreating
    rd /s /q .venv
  )
)

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
REM backend SUT deps (needed for real env)
if exist apps\backend\requirements.txt "%PY%" -m pip install -r apps\backend\requirements.txt -q

if not exist allure-results mkdir allure-results
if not exist reports mkdir reports
REM clean old artifacts, keep .gitignore
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
