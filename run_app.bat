@echo off
echo ========================================================
echo   ClassMon - Classroom Attention Monitor (Production)
echo ========================================================

echo 1. Starting FastAPI + React Dashboard...
start "ClassMon Server" cmd /k ".\.venv\Scripts\activate.bat && python scripts\start_classmon.py"

echo 2. Waiting 3 seconds for server to start...
timeout /t 3 /nobreak > nul

echo 3. Opening Dashboard in your browser...
start http://localhost:8000

echo 4. Starting Vision Pipeline (Webcam)...
start "ClassMon Vision" cmd /k ".\.venv\Scripts\activate.bat && python scripts\run_full_pipeline.py"

echo.
echo NOTE: Ensure Ollama is running in the background for Q&A scoring!
echo All systems started. Close the terminal windows to shut down.
pause
