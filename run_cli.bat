@echo off
echo ======================================================================
echo AMEVA-STT-Trainer Premium CLI Launcher
echo ======================================================================

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please setup venv and install requirements_cli.txt.
    pause
    exit /b
)

echo Starting AMEVA-STT-Trainer CLI...
venv\Scripts\python.exe cli\cli.py
pause
