# EdgeStream AI

A distributed video-on-demand streaming platform demonstrating:
- Distributed video delivery across three physical laptops
- Edge caching with Nginx (proxy cache + HLS segment caching)
- Adaptive Bitrate Streaming via hls.js
- AI-based buffering prediction using scikit-learn

---

## Network Map

| Machine    | Role              | IP (update these!)  | Port |
|------------|-------------------|---------------------|------|
| Laptop A   | Origin Server     | `192.168.1.10`      | 8000 |
| Laptop B   | Edge Server       | `192.168.1.20`      | 80   |
| Laptop C   | AI & Monitoring   | `192.168.1.30`      | 8001 |

> **IMPORTANT:** Update all three IPs in:
> - `origin-server/app/config.py` → `EDGE_IP`, `AI_SERVER_IP`
> - `edge-server/nginx.conf` → `proxy_pass`
> - `viewer-frontend/js/metrics.js` → `AI_SERVER`
> - `viewer-frontend/js/catalogue.js` → `EDGE_URL`, `ORIGIN_URL`

---

## Quick Start

### Laptop A — Origin Server

```powershell
# 1. Install FFmpeg — download from https://www.gyan.dev/ffmpeg/builds/
# 2. Extract to C:\ffmpeg\ and add C:\ffmpeg\bin to system PATH
# 3. Verify: ffmpeg -version

cd D:\Edgestream\origin-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy viewer frontend into static directory
xcopy /E /I ..\viewer-frontend ..\origin-server\static\viewer

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Admin UI:     http://192.168.1.10:8000/static/admin.html
Viewer UI:    http://192.168.1.20/static/viewer/index.html

### Laptop B — Edge Server

See `edge-server/README.md` for platform-specific Nginx setup.

### Laptop C — AI & Monitoring Server

```powershell
cd D:\Edgestream\ai-monitoring-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Dashboard:    http://192.168.1.30:8001/dashboard

---

## Project Structure

```
EdgeStream-AI/
├── origin-server/      # Laptop A — FastAPI + FFmpeg
├── edge-server/        # Laptop B — Nginx config
├── ai-monitoring-server/ # Laptop C — FastAPI + scikit-learn
├── viewer-frontend/    # Browser UI (served from Laptop A)
├── experiments/        # Experiment scripts and results
└── README.md
```

---

## Development Status

| Phase | Description                  | Status      |
|-------|------------------------------|-------------|
| 1     | Environment Setup            | ✅ Complete  |
| 2     | Origin Server                | ✅ Complete  |
| 3     | Edge Server                  | ✅ Complete  |
| 4     | Viewer Frontend              | ✅ Complete  |
| 5     | AI & Monitoring Server       | ✅ Complete  |
| 6     | Data Collection & Training   | ⬜ Pending   |
| 7     | Experiments                  | ⬜ Pending   |
| 8     | Demo Preparation             | ⬜ Pending   |
