# MyClaw Setup Script (Windows PowerShell)
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== MyClaw Setup ===" -ForegroundColor Cyan

# --- Backend ---
Write-Host "`n[1/4] Creating Python virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $ROOT "backend\.venv"
if (Test-Path $venvPath) {
    Write-Host "  Virtual environment already exists, skipping."
} else {
    python -m venv (Join-Path $ROOT "backend\.venv")
    Write-Host "  Created at backend\.venv"
}

Write-Host "`n[2/4] Installing Python dependencies..." -ForegroundColor Yellow
$pip = Join-Path $ROOT "backend\.venv\Scripts\pip.exe"
& $pip install -r (Join-Path $ROOT "backend\requirements.txt") --quiet
Write-Host "  Core dependencies installed."
& $pip install -r (Join-Path $ROOT "backend\requirements-skills.txt") --quiet
Write-Host "  Skill dependencies installed."

# --- Frontend ---
Write-Host "`n[3/4] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location (Join-Path $ROOT "frontend")
npm install --silent
Pop-Location
Write-Host "  Frontend dependencies installed."

# --- Verify ---
Write-Host "`n[4/4] Verifying installation..." -ForegroundColor Yellow
$py = Join-Path $ROOT "backend\.venv\Scripts\python.exe"
& $py -c "import langchain, duckdb, pandas; print(f'  langchain={langchain.__version__}, duckdb={duckdb.__version__}, pandas={pandas.__version__}')"

Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host @"

To start the services:

  Backend:
    cd backend
    .venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000

  Frontend:
    cd frontend
    npm run dev

Then open http://localhost:5173 in your browser.
"@
