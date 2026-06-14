@echo off

rem run_cli.bat - AMEVA-STT-Trainer CLI Launcher
rem Step 1: Check that venv exists
rem Step 2: Run hardware preflight (GPU/CUDA status)
rem Step 3: Check if API server is up on port 8600, auto-start if not
rem Step 4: Launch the interactive CLI

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

echo [INFO] Checking API server on port 8600...
netstat -ano | findstr :8600 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [WARN] API server not running. Starting in background...
    start "AMEVA API Server" run_server.bat
    echo [INFO] Waiting 5 seconds for server startup...
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] API server already running.
)
echo.

echo [INFO] Starting AMEVA-STT-Trainer CLI...
echo.
venv\Scripts\python.exe cli\cli.py
pause
