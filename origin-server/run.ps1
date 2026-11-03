# EdgeStream AI — Origin Server Startup Script (Windows PowerShell)
# Run this from the origin-server\ directory.
#
# Usage:
#   cd D:\Edgestream\origin-server
#   .\run.ps1

Write-Host "EdgeStream AI — Origin Server" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Activate virtual environment
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "ERROR: Virtual environment not found." -ForegroundColor Red
    Write-Host "Run: python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
    exit 1
}

# Verify FFmpeg is available
try {
    $null = & ffmpeg -version 2>&1
    Write-Host "FFmpeg: OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: FFmpeg not found on PATH." -ForegroundColor Red
    Write-Host "Download from: https://www.gyan.dev/ffmpeg/builds/"
    Write-Host "Extract to C:\ffmpeg\ and add C:\ffmpeg\bin to system PATH."
    exit 1
}

# Copy viewer frontend into static directory so FastAPI serves it
$viewerSrc = "..\viewer-frontend"
$viewerDst = ".\static\viewer"
if (Test-Path $viewerSrc) {
    Write-Host "Copying viewer frontend → $viewerDst" -ForegroundColor Yellow
    if (-not (Test-Path $viewerDst)) {
        New-Item -ItemType Directory -Path $viewerDst | Out-Null
    }
    Copy-Item -Path "$viewerSrc\*" -Destination $viewerDst -Recurse -Force
}

Write-Host ""
Write-Host "Starting origin server on port 8000..." -ForegroundColor Green
Write-Host "Admin UI:    http://localhost:8000/static/admin.html"
Write-Host "API docs:    http://localhost:8000/api/docs"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
