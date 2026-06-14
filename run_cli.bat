@echo off
chcp 65001 >nul
echo ==========================================================================
echo   AMEVA-STT-Trainer  ^|  Premium CLI Launcher
echo ==========================================================================
echo.

REM 가상환경 존재 여부 확인
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] 가상환경을 찾을 수 없습니다.
    echo [INFO]  setup\setup_env.ps1 을 먼저 실행하여 환경을 구축하세요.
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

REM ── [Step 2] 백엔드 API 서버 연결 확인 ────────────────────────────────────
echo [INFO] Checking if backend API server is running on port 8000...
netstat -ano | find "8000" >nul
if %errorlevel% neq 0 (
    echo [WARN] API 서버가 실행 중이 아닙니다. 자동으로 서버를 시작합니다...
    start "AMEVA API Server" run_server.bat
    echo [INFO] 서버 초기화 대기 중 (5초)...
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] API 서버가 이미 실행 중입니다!
)

REM ── [Step 3] Premium CLI 실행 ─────────────────────────────────────────────
echo [INFO] Starting AMEVA-STT-Trainer Premium CLI...
echo.
venv\Scripts\python.exe cli\cli.py
pause
