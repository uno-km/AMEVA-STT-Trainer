# AMEVA-STT-Trainer Virtual Environment Setup Script

Write-Host "Creating Virtual Environment (venv)..." -ForegroundColor Cyan
python -m venv venv

Write-Host "Activating Virtual Environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt
pip install python-docx matplotlib pandas # 리포트 생성용 추가

Write-Host "Verifying WandB installation..." -ForegroundColor Cyan
python -c "import wandb; print(f'WandB Version: {wandb.__version__}')"

# --- whisper.cpp 변환 도구 세팅 ---
$ThirdPartyDir = "third_party"
$WhisperCppDir = "$ThirdPartyDir/whisper.cpp"

if (-not (Test-Path $ThirdPartyDir)) {
    New-Item -ItemType Directory -Path $ThirdPartyDir | Out-Null
}

if (-not (Test-Path $WhisperCppDir)) {
    Write-Host "Cloning whisper.cpp for conversion tools..." -ForegroundColor Cyan
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git $WhisperCppDir
} else {
    Write-Host "whisper.cpp already exists in $WhisperCppDir" -ForegroundColor Gray
}

Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "To activate the environment in the future, run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
