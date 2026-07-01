@echo off
REM 接口自动化测试 — 一键运行脚本（Windows）

echo === 1. 安装依赖 ===
pip install -r requirements.txt -q

echo === 2. 启动 Mock 服务 ===
start /B python core\mock_server.py
timeout /t 2 /nobreak >nul

echo === 3. 运行测试 ===
python -m pytest tests/ -v --tb=short

echo === 4. 清理 Mock 服务 ===
taskkill /F /IM python.exe >nul 2>&1

echo === 完成 ===
pause