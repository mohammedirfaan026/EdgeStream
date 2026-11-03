# EdgeStream AI — AI & Monitoring Server Startup Script (Windows PowerShell)
# Run this from the ai-monitoring-server\ directory.
#
# Usage:
#   cd D:\Edgestream\ai-monitoring-server
#   .\run.ps1

Write-Host "EdgeStream AI — AI & Monitoring Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Activate virtual environment
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "ERROR: Virtual environment not found." -ForegroundColor Red
    Write-Host "Run: python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
    exit 1
}

# Check model status
if (Test-Path ".\models\model.joblib") {
    Write-Host "ML model: Found — will use trained model" -ForegroundColor Green
} else {
    Write-Host "ML model: Not found — will use 2-second buffer baseline" -ForegroundColor Yellow
    Write-Host "          (Run scripts/train.py after collecting data to train the model)"
}

Write-Host ""
Write-Host "Starting AI server on port 8001..." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:8001/dashboard"
Write-Host "API docs:  http://localhost:8001/api/docs"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
