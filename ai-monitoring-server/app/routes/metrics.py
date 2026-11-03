"""
metrics.py — /metrics/ingest endpoint.

This is the most important endpoint on the AI server.
It is called by every browser player every 5 seconds with playback telemetry.

Responsibilities:
  1. Validate the incoming payload.
  2. Upsert the session record.
  3. Insert the playback event.
  4. Detect and record buffering episodes.
  5. Extract features and run the prediction model.
  6. Store the prediction.
  7. Return the risk score to the browser.

The entire operation is kept fast (<100 ms) because the browser is waiting
for the response before showing/hiding the warning overlay.
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_connection
from app.monitoring.event_processor import process_buffering
from app.prediction import features as feat_module
from app.prediction import model as model_module

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ── Request model ─────────────────────────────────────────────────────────────

class MetricsPayload(BaseModel):
    """
    Telemetry data sent by metrics.js every REPORT_INTERVAL_MS.
    All numeric fields are optional so a partial metric is still recorded.
    """
    session_id:        str   = Field(..., min_length=1, max_length=128)
    video_id:          str   = Field(..., min_length=1, max_length=128)
    timestamp:         str   = Field(..., description="ISO 8601 timestamp")
    playback_time_s:   Optional[float] = None
    buffer_duration_s: Optional[float] = Field(None, ge=0)
    bitrate_kbps:      Optional[float] = Field(None, ge=0)
    dl_speed_kbps:     Optional[float] = Field(None, ge=0)
    dl_time_ms:        Optional[float] = Field(None, ge=0)
    is_buffering:      bool  = False
    quality_level:     Optional[int]   = None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/ingest")
def ingest_metrics(payload: MetricsPayload) -> dict:
    """
    Receive one telemetry snapshot from a browser player.
    Returns the AI prediction result so the browser can update its warning overlay.
    """
    sid = payload.session_id
    vid = payload.video_id

    # ── 1. Upsert session ──────────────────────────────────────────────────────
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?", (sid,)
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT INTO sessions (session_id, video_id) VALUES (?, ?)",
                (sid, vid),
            )
        else:
            conn.execute(
                "UPDATE sessions SET last_seen = datetime('now'), is_active = 1 WHERE session_id = ?",
                (sid,),
            )

    # ── 2. Insert playback event ───────────────────────────────────────────────
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO playback_events
               (session_id, playback_time_s, buffer_s, bitrate_kbps,
                dl_speed_kbps, dl_time_ms, is_buffering, quality_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sid,
                payload.playback_time_s,
                payload.buffer_duration_s,
                payload.bitrate_kbps,
                payload.dl_speed_kbps,
                payload.dl_time_ms,
                1 if payload.is_buffering else 0,
                payload.quality_level,
            ),
        )

    # ── 3. Detect buffering episode ────────────────────────────────────────────
    process_buffering(sid, payload.is_buffering, payload.buffer_duration_s or 0)

    # ── 4. Extract features ────────────────────────────────────────────────────
    features = feat_module.extract_features(sid, payload.model_dump())

    # ── 5. Run prediction ──────────────────────────────────────────────────────
    label, risk_score, source = model_module.predict(features)

    # ── 6. Store prediction ────────────────────────────────────────────────────
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO predictions
               (session_id, risk_score, predicted_label, model_version, features_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                sid,
                risk_score,
                label,
                source,
                json.dumps(features),
            ),
        )

    # ── 7. Return result ───────────────────────────────────────────────────────
    return {
        "received": True,
        "buffering_risk_score": risk_score,
        "warning": bool(label == 1),
        "prediction_label": "HIGH" if label == 1 else "LOW",
        "prediction_source": source,   # "model" or "baseline"
    }


@router.get("/sessions")
def list_sessions() -> list:
    """List all active playback sessions."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.session_id, s.video_id, s.started_at, s.last_seen,
                      COUNT(e.id) as event_count
               FROM sessions s
               LEFT JOIN playback_events e ON e.session_id = s.session_id
               WHERE s.is_active = 1
               GROUP BY s.session_id
               ORDER BY s.last_seen DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
