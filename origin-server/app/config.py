"""
config.py — All configurable settings for the Origin Server.

Change the IP addresses below to match your actual LAN setup.
Do NOT hardcode IPs or paths anywhere else in the codebase —
always import from this file.
"""
import os
from pathlib import Path

# ─── Directory paths ───────────────────────────────────────────────────────────
# BASE_DIR is the root of the origin-server/ folder
BASE_DIR      = Path(__file__).parent.parent
UPLOAD_DIR    = BASE_DIR / "uploads"       # raw uploaded video files
PROCESSED_DIR = BASE_DIR / "processed"    # FFmpeg HLS output
STATIC_DIR    = BASE_DIR / "static"       # admin UI + viewer frontend
DB_PATH       = BASE_DIR / "origin.db"    # SQLite database

# ─── Network settings ──────────────────────────────────────────────────────────
ORIGIN_HOST = "0.0.0.0"   # bind to all interfaces so LAN can reach it
ORIGIN_PORT = 8000

# IP addresses of other machines — UPDATE THESE to your real LAN IPs
EDGE_IP      = os.getenv("EDGE_IP",      "192.168.1.20")   # Laptop B
AI_SERVER_IP = os.getenv("AI_SERVER_IP", "192.168.1.30")   # Laptop C

# ─── FFmpeg settings ───────────────────────────────────────────────────────────
# If ffmpeg is not on system PATH, set the FFMPEG_BIN environment variable
# to the full path, e.g. "C:\\ffmpeg\\bin\\ffmpeg.exe"
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

# Duration of each HLS segment in seconds (4–6 seconds is standard for VOD)
SEGMENT_DURATION = 4

# Resolutions to generate: (label, width, height, video_bitrate_kbps)
# The label is used in filenames: e.g. seg_00001_360p.ts
RESOLUTIONS = [
    ("360p",  640,  360,  800),
    ("480p",  854,  480, 1400),
    ("720p", 1280,  720, 2800),
]

# ─── Upload validation ─────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB  = 500
ALLOWED_EXTENSIONS  = {".mp4", ".mkv", ".mov", ".avi"}

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow all LAN origins so the browser player can fetch HLS files
CORS_ORIGINS = ["*"]
