# ======================================================================
# AMEVA-STT-Trainer Virtual Environment Setup Script (Windows PowerShell)
# ======================================================================

Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   AMEVA-STT-Trainer Windows Auto-Installer" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta

# 1. Create Virtual Environment
if (-not (Test-Path "venv")) {
    Write-Host "[1/5] Creating Virtual Environment (venv)..." -ForegroundColor Cyan
    python -m venv venv
} else {
    Write-Host "[1/5] Virtual Environment already exists." -ForegroundColor Gray
}

# 2. Activate Virtual Environment
Write-Host "[2/5] Activating Virtual Environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# 3. Upgrade pip
Write-Host "[3/5] Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# 4. Install Dependencies
Write-Host "[4/5] Installing core dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

# 5. Verify Installations
Write-Host "Verifying installations..." -ForegroundColor Cyan
python -c "import wandb; print(f'  WandB Version: {wandb.__version__}')"
python -c "import gguf; print('  GGUF-Py: Fully Verified')"

# --- whisper.cpp & Quantization Utilities Configuration ---
$ThirdPartyDir = "third_party"
$WhisperCppDir = "$ThirdPartyDir/whisper.cpp"

if (-not (Test-Path $ThirdPartyDir)) {
    New-Item -ItemType Directory -Path $ThirdPartyDir | Out-Null
}

if (-not (Test-Path $WhisperCppDir)) {
    Write-Host "[5/5] Cloning whisper.cpp for conversion and quantization tools..." -ForegroundColor Cyan
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git $WhisperCppDir
} else {
    Write-Host "[5/5] whisper.cpp already exists in $WhisperCppDir" -ForegroundColor Gray
}

# Verify Precompiled Quantization Binaries for Windows
$QuantizeExe = "$WhisperCppDir/quantize.exe"
if (Test-Path $QuantizeExe) {
    Write-Host "[SUCCESS] Precompiled Windows 'quantize.exe' utility found!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Precompiled 'quantize.exe' was not found in $WhisperCppDir." -ForegroundColor Yellow
    Write-Host "Please download the precompiled binary or compile it manually inside $WhisperCppDir." -ForegroundColor Yellow
}

Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "To activate the environment in the future, run:" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "To view GGUF conversion instructions, run:" -ForegroundColor Yellow
Write-Host "   python scripts/export_gguf.py" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Magenta
