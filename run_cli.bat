@echo off
rem ============================================================
rem run_cli.bat - AMEVA-STT-Trainer Premium CLI Launcher
rem
rem 실행 흐름:
rem   1. 가상환경(venv) 존재 여부 확인
rem   2. 하드웨어 프리플라이트 진단 (GPU/CUDA/PyTorch 상태 점검)
rem   3. 백엔드 API 서버(포트 8600) 연결 확인 - 없으면 자동 기동
rem   4. CLI 메인 진입점 실행
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

rem --- Step 2: Backend API Server Check ---
rem 포트 8600 바인딩 여부 확인 후 없으면 run_server.bat 을 백그라운드로 기동
echo [INFO] Checking backend API server on port 8600...
netstat -ano | find "8600" >nul
if %errorlevel% neq 0 (
    echo [WARN] API server not running. Starting server in background...
    start "AMEVA API Server" run_server.bat
    echo [INFO] Waiting 5 seconds for server to initialize...
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] API server is already running.
)
echo.

rem --- Step 3: Launch CLI ---
echo [INFO] Starting AMEVA-STT-Trainer Premium CLI...
echo.
venv\Scripts\python.exe cli\cli.py
pause
