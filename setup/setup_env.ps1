# ======================================================================
# AMEVA-STT-Trainer Virtual Environment Setup Script (Windows PowerShell)
# ======================================================================

Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   AMEVA-STT-Trainer Windows Auto-Installer" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta

# 1. Create Virtual Environment
if (-not (Test-Path "venv")) {
    Write-Host "[1/5] 가상 환경(venv) 생성 중..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "[✓] 가상 환경 생성 완료!" -ForegroundColor Green
} else {
    Write-Host "[✓] 가상 환경이 이미 존재합니다." -ForegroundColor Green
}

# 2. Activate Virtual Environment
Write-Host "[2/5] 가상 환경 활성화 중..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1
Write-Host "[✓] 가상 환경 활성화 완료!" -ForegroundColor Green

# 3. Upgrade pip
Write-Host "[3/5] pip 업그레이드 중..." -ForegroundColor Cyan
python -m pip install --upgrade pip
Write-Host "[✓] pip 업그레이드 완료!" -ForegroundColor Green

# 4. Install Dependencies
Write-Host "[4/5] requirements.txt 패키지 의존성 설치 중..." -ForegroundColor Cyan
pip install -r requirements.txt
Write-Host "[✓] 패키지 설치 완료!" -ForegroundColor Green

# 5. Verify Installations
Write-Host "설치 라이브러리 검증 및 확인 중..." -ForegroundColor Cyan
python -c "import wandb; print(f'  [✓] WandB 확인 완료 (버전: {wandb.__version__})')"
python -c "import gguf; print('  [✓] GGUF-Py 확인 완료')"

# 6. Interactive Model Download
python setup/download_models_interactive.py

# --- whisper.cpp & Quantization Utilities Configuration ---
$ThirdPartyDir = "third_party"
$WhisperCppDir = "$ThirdPartyDir/whisper.cpp"

if (-not (Test-Path $ThirdPartyDir)) {
    New-Item -ItemType Directory -Path $ThirdPartyDir | Out-Null
}

if (-not (Test-Path $WhisperCppDir)) {
    Write-Host "[5/5] whisper.cpp 리포지토리 클론 중..." -ForegroundColor Cyan
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git $WhisperCppDir
    Write-Host "[✓] whisper.cpp 클론 완료!" -ForegroundColor Green
} else {
    Write-Host "[✓] whisper.cpp가 이미 존재합니다: $WhisperCppDir" -ForegroundColor Green
}

# Verify Precompiled Quantization Binaries for Windows
$QuantizeExe = "$WhisperCppDir/quantize.exe"
if (Test-Path $QuantizeExe) {
    Write-Host "[✓] Windows 전용 'quantize.exe' 컴파일 유틸리티 감지 완료!" -ForegroundColor Green
} else {
    Write-Host "[!] 'quantize.exe'를 $WhisperCppDir 에서 찾을 수 없습니다." -ForegroundColor Yellow
    Write-Host "양자화 기능을 사용하려면 수동 컴파일 또는 바이너리 배치가 필요합니다." -ForegroundColor Yellow
}

Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "To activate the environment in the future, run:" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "To view GGUF conversion instructions, run:" -ForegroundColor Yellow
Write-Host "   python scripts/export_gguf.py" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Magenta
