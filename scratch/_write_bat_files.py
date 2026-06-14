"""
_write_bat_files.py
BAT 파일들을 순수 ASCII 로 재작성하는 임시 유틸리티 스크립트.
BAT 파일에 한글(비ASCII 문자)이 들어가면 Windows cmd.exe 가 CP949 로 파싱하면서
UTF-8 한글 바이트를 명령어로 해석하여 오류가 발생한다.
이 스크립트는 세 개의 BAT 파일을 완전한 ASCII 로 새로 씁니다.
"""

# run_cli.bat: CLI 런처
CLI_BAT = """\
@echo off

rem run_cli.bat - AMEVA-STT-Trainer CLI Launcher
rem Step 1: Check that venv exists
rem Step 2: Run hardware preflight (GPU/CUDA status)
rem Step 3: Check if API server is up on port 8600, auto-start if not
rem Step 4: Launch the interactive CLI

IF NOT EXIST "venv\\Scripts\\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [INFO]  Run: python setup.py
    pause
    exit /b 1
)

echo [PREFLIGHT] Running hardware check...
venv\\Scripts\\python.exe scripts\\check_hardware.py
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
venv\\Scripts\\python.exe cli\\cli.py
pause
"""

# run_server.bat: FastAPI 백엔드 서버 런처
SERVER_BAT = """\
@echo off

rem run_server.bat - AMEVA-STT-Trainer Backend API Server
rem Step 1: Check venv exists
rem Step 2: Hardware preflight
rem Step 3: Start FastAPI on port 8600

IF NOT EXIST "venv\\Scripts\\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo [INFO]  Run: python setup.py
    pause
    exit /b 1
)

echo [PREFLIGHT] Running hardware check...
venv\\Scripts\\python.exe scripts\\check_hardware.py
IF %errorlevel% NEQ 0 (
    echo [WARN] Hardware check had errors. Continuing.
)
echo.

echo [INFO] Starting FastAPI server on 0.0.0.0:8600
venv\\Scripts\\python.exe -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8600

pause
"""

# run_web_cli.bat: 다른 기기에서 브라우저로 CLI 화면을 볼 수 있는 공유 런처
# ttyd 를 통해 웹 터미널을 개방한다 (학습 진행상황을 다른 환경에서 모니터링)
WEB_CLI_BAT = """\
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

IF NOT EXIST "venv\\Scripts\\python.exe" (
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
ttyd.exe -p 8080 -W venv\\Scripts\\python.exe cli\\cli.py

pause
"""


def write_ascii(filename, content):
    """파일을 ASCII 인코딩으로 강제 저장. 비ASCII 문자 포함 시 오류 발생."""
    # 비ASCII 문자가 있는지 먼저 확인
    for i, ch in enumerate(content):
        if ord(ch) > 127:
            raise ValueError(f"Non-ASCII character at position {i}: {repr(ch)}")
    with open(filename, "w", encoding="ascii", newline="\r\n") as f:
        f.write(content)
    print(f"  [OK] {filename} written ({len(content)} bytes, pure ASCII)")


if __name__ == "__main__":
    print("\nWriting ASCII-only BAT files...")
    write_ascii("run_cli.bat", CLI_BAT)
    write_ascii("run_server.bat", SERVER_BAT)
    write_ascii("run_web_cli.bat", WEB_CLI_BAT)
    print("\nAll done. BAT files are now pure ASCII.\n")
