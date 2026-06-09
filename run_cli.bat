@echo off
echo ======================================================================
echo AMEVA-STT-Trainer Premium CLI Launcher
echo ======================================================================

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please setup venv and install requirements_cli.txt.
    pause
    exit /b
)

echo [INFO] Checking if backend API server is running on port 8000...
netstat -ano | find "8000" >nul
if %errorlevel% neq 0 (
    echo [WARN] API server is not running. Automatically starting the server...
    start "AMEVA API Server" run_server.bat
    echo [INFO] Waiting 5 seconds for the server to initialize...
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] API server is already running!
)

echo Starting AMEVA-STT-Trainer CLI...
venv\Scripts\python.exe cli\cli.py
pause
