@echo off
echo ==============================================
echo AMEVA-STT-Trainer Headless API Server
echo ==============================================
echo.

REM 가상환경 활성화 (필요 시 수정)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [INFO] Starting FastAPI server on 0.0.0.0:8000
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000

pause
