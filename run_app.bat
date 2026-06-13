@echo off
cd /d "%~dp0backend"

echo.
echo === Starting AIPulse App ===
echo.

REM Open browser tab after server has time to start (uses Python's built-in webbrowser module)
start /b python -c "import time, webbrowser; time.sleep(5); webbrowser.open('http://localhost:8000')"

REM Start the FastAPI server
echo Starting server at http://localhost:8000 ...
echo Press Ctrl+C to stop.
echo.
cd src
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
