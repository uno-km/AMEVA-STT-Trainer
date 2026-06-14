@echo off

rem run_server.bat - AMEVA-STT-Trainer Backend API Server
rem Step 1: Check venv exists
rem Step 2: Hardware preflight
rem Step 3: Start FastAPI on port 8600

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [INFO]  Run: python setup.py
    pause
    exit /b 1
)

echo [PREFLIGHT] Running hardware check...
venv\Scripts\python.exe scripts\check_hardware.py
IF %errorlevel% NEQ 0 (
    echo [WARN] Hardware check had errors. Continuing.
)
echo.

echo [INFO] Starting FastAPI server on 0.0.0.0:8600
venv\Scripts\python.exe -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8600

pause
