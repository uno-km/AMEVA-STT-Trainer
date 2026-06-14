# AMEVA STT Trainer 실행 및 환경 진단 스크립트

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ($ScriptPath) { Set-Location -Path $ScriptPath }

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($PSVersionTable.PSVersion.Major -le 5) { chcp 65001 | Out-Null }
$ErrorActionPreference = "Stop"

Write-Host "--- AMEVA STT Trainer Environment Setup ---" -ForegroundColor Cyan
Write-Host "Path: $(Get-Location)" -ForegroundColor Gray

# [1] 가상환경(venv) 존재 검증
$EnvDir = ".\venv"
if (-not (Test-Path -Path $EnvDir)) {
    Write-Host "Virtual environment (venv) not found. Running setup.py first..." -ForegroundColor Yellow
    & python setup.py
    if (-not (Test-Path -Path $EnvDir)) {
        Write-Error "Virtual environment setup failed."
        exit 1
    }
}

# [2] 하드웨어 체크 (선택 단계)
$pythonExe = "$EnvDir\Scripts\python.exe"
if (Test-Path "$ScriptPath\scripts\check_hardware.py") {
    Write-Host "Running hardware preflight..." -ForegroundColor Cyan
    & $pythonExe scripts\check_hardware.py
}

# [3] 8600 포트 API 서버 기동 상태 검사
Write-Host "Checking API server on port 8600..." -ForegroundColor Cyan
$proc = Get-NetTCPConnection -LocalPort 8600 -State Listen -ErrorAction SilentlyContinue

if (-not $proc) {
    Write-Host "API server is not running. Starting backend API server in background..." -ForegroundColor Yellow
    # 백그라운드로 uvicorn 가동
    Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn src.backend.main:app --host 0.0.0.0 --port 8600" -WindowStyle Hidden
    Write-Host "Waiting 5 seconds for server startup..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
} else {
    Write-Host "API server is already running." -ForegroundColor Green
}

# [4] 가상환경 활성화 단계
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. "$EnvDir\Scripts\Activate.ps1"

# [5] 메인 CLI 어플리케이션 기동
Write-Host "Launching AMEVA STT Trainer CLI..." -ForegroundColor Cyan
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

& "$EnvDir\Scripts\python.exe" cli/cli.py
