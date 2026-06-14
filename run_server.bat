@echo off
rem ============================================================
rem run_server.bat - AMEVA-STT-Trainer Backend API Server
rem
rem 실행 흐름:
rem   1. 가상환경(venv) 존재 여부 확인
rem   2. 하드웨어 프리플라이트 진단 (GPU/CUDA 상태 점검)
rem   3. FastAPI 백엔드 서버를 포트 8600 으로 기동
rem ============================================================

rem 가상환경 확인
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [INFO]  Please run: python setup.py
    pause
    exit /b 1
)

rem --- Step 1: Hardware Preflight Check ---
echo [PREFLIGHT] Running hardware diagnostic...
venv\Scripts\python.exe scripts\check_hardware.py
IF %errorlevel% NEQ 0 (
    echo [WARN] Hardware diagnostic exited with errors. Continuing anyway.
)
echo.

rem --- Step 2: Launch FastAPI Backend ---
rem 포트 8600 으로 uvicorn FastAPI 서버 기동
echo [INFO] Starting FastAPI server on 0.0.0.0:8600
venv\Scripts\python.exe -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8600

pause
