# AMEVA-STT-Trainer Virtual Environment Setup Script

Write-Host "Creating Virtual Environment (venv)..." -ForegroundColor Cyan
python -m venv venv

Write-Host "Activating Virtual Environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "To activate the environment in the future, run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
