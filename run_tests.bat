@echo off
echo === 1. Install dependencies ===
pip install -r requirements.txt -q

echo === 2. Run tests ===
python -m pytest tests/ -v --tb=short

echo === Done ===
pause
