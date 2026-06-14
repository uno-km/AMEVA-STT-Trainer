@echo off
chcp 65001 >nul
echo ==========================================================================
echo   AMEVA-STT-Trainer  ^|  Server Launcher
echo ==========================================================================
echo.

REM 가상환경 존재 여부 확인
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] 가상환경을 찾을 수 없습니다. setup\setup_env.ps1 을 먼저 실행하세요.
    pause
    exit /b 1
)

REM ── [Step 1] 하드웨어 프리플라이트 진단 ──────────────────────────────────
echo [PREFLIGHT] 하드웨어 환경 진단 중...
venv\Scripts\python.exe scripts\check_hardware.py
IF %errorlevel% NEQ 0 (
    echo [WARN] 하드웨어 진단이 비정상 종료되었습니다. 계속 진행합니다...
)
echo.

REM ── [Step 2] FastAPI 백엔드 서버 기동 ─────────────────────────────────────
echo [INFO] Starting FastAPI server on 0.0.0.0:8600
venv\Scripts\python.exe -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8600

pause
