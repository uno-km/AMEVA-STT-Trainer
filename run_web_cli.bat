@echo off
rem ============================================================
rem run_web_cli.bat - AMEVA-STT-Trainer Web Terminal Sharing
rem
rem 다른 환경(같은 네트워크 내 다른 PC, 태블릿, 스마트폰 등)에서
rem 웹 브라우저로 이 CLI 터미널에 접속하여 학습 진행상황을 볼 수 있습니다.
rem
rem 사전 준비:
rem   ttyd.exe 를 아래 링크에서 받아 이 폴더 또는 PATH 에 배치하세요.
rem   https://github.com/tsl0922/ttyd/releases
rem
rem 접속 방법:
rem   같은 네트워크의 다른 기기에서 브라우저로
rem   http://<이 PC의 IP주소>:8680 으로 접속하면 됩니다.
rem ============================================================

rem ttyd 실행 파일 존재 여부 확인
IF NOT EXIST "ttyd.exe" (
    where ttyd >nul 2>&1
    IF %errorlevel% NEQ 0 (
        echo [ERROR] ttyd.exe not found.
        echo [INFO]  Download from: https://github.com/tsl0922/ttyd/releases
        echo [INFO]  Place ttyd.exe in this folder, then run again.
        pause
        exit /b 1
    )
)

rem 가상환경 확인
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run python setup.py first.
    pause
    exit /b 1
)

rem --- Launch Web Terminal ---
rem 포트 8680 으로 CLI 터미널을 웹에 공유 (read-write 접근 허용)
echo [INFO] Starting web terminal sharing on port 8680...
echo [INFO] Open http://YOUR_IP_ADDRESS:8680 in any browser on the same network.
echo [INFO] Press Ctrl+C to stop sharing.
echo.
ttyd.exe -p 8680 -W venv\Scripts\python.exe cli\cli.py

pause
