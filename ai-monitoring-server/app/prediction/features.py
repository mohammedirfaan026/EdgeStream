"""
features.py — Extracts feature vectors from raw telemetry metrics.

The feature set used for model training and inference:
  buffer_s      — current buffer duration in seconds (primary signal)
  bitrate_kbps  — current estimated playback bitrate
  dl_speed_kbps — recent segment download throughput
  dl_time_ms    — recent segment download time
  buffer_trend  — change in buffer level over the last 3 readings
                  (positive = buffer growing, negative = shrinking)

buffer_trend requires reading recent history from the DB, so it cannot
come from the telemetry payload alone.

IMPORTANT: All features must be available AT prediction time.
Do not use any future-event data as a feature (that would be data leakage).
"""
import sqlite3
import json
from app.config import DB_PATH

# Names must match exactly what train.py uses
FEATURE_NAMES = ["buffer_s", "bitrate_kbps", "dl_speed_kbps", "dl_time_ms", "buffer_trend"]


def extract_features(session_id: str, current: dict) -> dict:
    """
    Build the feature dict for a single prediction from current telemetry
    plus a short history query from the DB.

    Parameters
    ----------
    session_id : str
        The session we are predicting for.
    current : dict
        The current telemetry payload (already validated by the API layer).

    Returns
    -------
    dict with keys matching FEATURE_NAMES
    """
    buffer_now = float(current.get("buffer_duration_s") or 0)
    bitrate    = float(current.get("bitrate_kbps") or 0)
    dl_speed   = float(current.get("dl_speed_kbps") or 0)
    dl_time    = float(current.get("dl_time_ms") or 0)

    # ── Buffer trend: change over last 3 readings for this session ─────────────
    buffer_trend = _compute_buffer_trend(session_id, buffer_now)

    features = {
        "buffer_s":      buffer_now,
        "bitrate_kbps":  bitrate,
        "dl_speed_kbps": dl_speed,
        "dl_time_ms":    dl_time,
        "buffer_trend":  buffer_trend,
    }
    return features


def features_to_list(features: dict) -> list:
    """Convert feature dict to an ordered list matching FEATURE_NAMES."""
    return [features[name] for name in FEATURE_NAMES]


def _compute_buffer_trend(session_id: str, buffer_now: float) -> float:
    """
    Compute buffer trend as: buffer_now - buffer_oldest_in_window.

    Reads the last 3 buffer_s values from the DB for this session.
    If fewer than 2 readings exist, trend is 0 (not enough history).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT buffer_s FROM playback_events
               WHERE session_id = ?
               ORDER BY recorded_at DESC
               LIMIT 3""",
            (session_id,),
        ).fetchall()
        conn.close()

        if len(rows) >= 2:
            # rows[0] is the most recent PREVIOUS reading (current hasn't been saved yet)
            oldest = rows[-1]["buffer_s"] or 0
            return round(buffer_now - oldest, 3)
        return 0.0

    except Exception:
        return 0.0
