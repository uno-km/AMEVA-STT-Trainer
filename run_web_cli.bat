@echo off

rem run_web_cli.bat - AMEVA-STT-Trainer Web Terminal Sharing
rem
rem This lets you watch the CLI training progress from any browser
rem on the same network. Uses ttyd to expose the terminal over HTTP.
rem
rem Download ttyd.exe from: https://github.com/tsl0922/ttyd/releases
rem Place ttyd.exe in this folder or in your system PATH.
rem
rem Access from another device:  http://<THIS_PC_IP>:8080

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run python setup.py first.
    pause
    exit /b 1
)

ttyd.exe --version >nul 2>&1
IF %errorlevel% NEQ 0 (
    where ttyd >nul 2>&1
    IF %errorlevel% NEQ 0 (
        echo [ERROR] ttyd.exe not found in this folder or PATH.
        echo [INFO]  Download: https://github.com/tsl0922/ttyd/releases
        echo [INFO]  Place ttyd.exe here, then run this script again.
        pause
        exit /b 1
    )
)

echo [INFO] Starting web terminal on port 8080...
echo [INFO] Open http://YOUR_PC_IP_ADDRESS:8080 in any browser.
echo [INFO] Press Ctrl+C to stop.
echo.
ttyd.exe -p 8080 -W venv\Scripts\python.exe cli\cli.py

pause
