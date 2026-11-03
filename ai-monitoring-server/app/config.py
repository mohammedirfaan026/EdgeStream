"""
config.py — All configurable settings for the AI & Monitoring Server.

Change the values below to match your actual network and preferences.
All other modules import from here — do not hardcode values elsewhere.
"""
import os
from pathlib import Path

# ─── Directory paths ───────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
DB_PATH     = BASE_DIR / "edgestream.db"
MODEL_PATH  = BASE_DIR / "models" / "model.joblib"
DATA_DIR    = BASE_DIR / "data"
STATIC_DIR  = BASE_DIR / "static"

# ─── Server settings ──────────────────────────────────────────────────────────
AI_HOST = "0.0.0.0"
AI_PORT = 8001

# ─── Prediction settings ──────────────────────────────────────────────────────
# Probability threshold above which a prediction is flagged as HIGH risk.
# Lower value → more sensitive (higher recall, more false alarms).
# Start with 0.45 and tune after evaluating on real data.
PREDICTION_THRESHOLD = float(os.getenv("PREDICTION_THRESHOLD", "0.45"))

# How many seconds ahead to look for a buffering event when creating labels.
LOOKAHEAD_SECONDS = int(os.getenv("LOOKAHEAD_SECONDS", "10"))

# ─── Baseline rule ────────────────────────────────────────────────────────────
# Simple rule-based baseline: predict buffering risk if buffer < this value (seconds).
BASELINE_BUFFER_THRESHOLD_S = float(os.getenv("BASELINE_BUFFER_S", "2.0"))

# ─── Data retention ───────────────────────────────────────────────────────────
# How many days of playback events to keep in the DB.
METRICS_RETENTION_DAYS = int(os.getenv("METRICS_RETENTION_DAYS", "30"))

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS = ["*"]   # open for LAN prototype
