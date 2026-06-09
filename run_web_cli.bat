@echo off
echo ==============================================
echo AMEVA-STT-Trainer Web CLI Sharing (ttyd)
echo ==============================================
echo.
echo [INFO] 웹 브라우저를 통해 CLI 터미널을 공유합니다.
echo [INFO] 주의: ttyd.exe가 시스템 PATH에 있거나 현재 폴더에 있어야 합니다.
echo [INFO] https://github.com/tsl0922/ttyd/releases 에서 윈도우용 빌드를 받아주세요.
echo.

REM 포트 8080으로 CLI 접속을 허용합니다.
ttyd.exe -p 8080 cmd.exe /c "python cli/cli.py"

pause
