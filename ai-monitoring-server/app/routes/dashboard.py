"""
dashboard.py — Endpoints that supply data to the monitoring dashboard.

GET /dashboard       → serves the dashboard HTML page
GET /dashboard/data  → JSON data for all dashboard panels (polled by browser)
POST /cache-stats    → ingest edge cache statistics from the experiment script
"""
import json
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import STATIC_DIR
from app.database import get_connection

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """Serve the monitoring dashboard HTML page."""
    return FileResponse(STATIC_DIR / "dashboard.html")


@router.get("/dashboard/data")
def get_dashboard_data() -> dict:
    """
    Aggregate all metrics needed by the dashboard.
    Called by dashboard.js every 5 seconds via polling.
    Designed to be fast — all queries are simple aggregations on indexed tables.
    """
    with get_connection() as conn:

        # ── Streaming metrics ──────────────────────────────────────────────────
        active_sessions = conn.execute(
            "SELECT COUNT(*) as cnt FROM sessions WHERE is_active = 1"
        ).fetchone()["cnt"]

        total_sessions = conn.execute(
            "SELECT COUNT(*) as cnt FROM sessions"
        ).fetchone()["cnt"]

        avg_buffer = conn.execute(
            "SELECT AVG(buffer_s) as avg FROM playback_events "
            "WHERE buffer_s IS NOT NULL"
        ).fetchone()["avg"] or 0

        total_buffering_events = conn.execute(
            "SELECT COUNT(*) as cnt FROM buffering_events"
        ).fetchone()["cnt"]

        # ── Recent buffer trend (last 60 readings across all sessions) ─────────
        recent_buffer = conn.execute(
            """SELECT recorded_at, buffer_s
               FROM playback_events
               WHERE buffer_s IS NOT NULL
               ORDER BY recorded_at DESC
               LIMIT 60"""
        ).fetchall()
        recent_buffer_list = [
            {"t": r["recorded_at"], "v": round(r["buffer_s"], 2)}
            for r in reversed(recent_buffer)
        ]

        # ── AI predictions ─────────────────────────────────────────────────────
        recent_predictions = conn.execute(
            """SELECT predicted_at, risk_score, predicted_label, model_version
               FROM predictions
               ORDER BY predicted_at DESC
               LIMIT 20"""
        ).fetchall()
        predictions_list = [dict(r) for r in recent_predictions]

        high_risk_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM predictions WHERE predicted_label = 1"
        ).fetchone()["cnt"]

        total_predictions = conn.execute(
            "SELECT COUNT(*) as cnt FROM predictions"
        ).fetchone()["cnt"]

        # ── Cache statistics (from experiment script) ──────────────────────────
        cache_row = conn.execute(
            """SELECT SUM(hits) as h, SUM(misses) as m, SUM(total) as t
               FROM cache_stats"""
        ).fetchone()
        cache_hits   = cache_row["h"] or 0
        cache_misses = cache_row["m"] or 0
        cache_total  = cache_row["t"] or (cache_hits + cache_misses)
        hit_ratio    = round(cache_hits / cache_total, 4) if cache_total > 0 else 0

    return {
        "streaming": {
            "active_sessions":        active_sessions,
            "total_sessions":         total_sessions,
            "avg_buffer_s":           round(float(avg_buffer), 2),
            "total_buffering_events": total_buffering_events,
            "recent_buffer_series":   recent_buffer_list,
        },
        "cache": {
            "hits":       cache_hits,
            "misses":     cache_misses,
            "total":      cache_total,
            "hit_ratio":  hit_ratio,
        },
        "ai": {
            "total_predictions":   total_predictions,
            "high_risk_count":     high_risk_count,
            "recent_predictions":  predictions_list,
        },
    }


@router.post("/cache-stats", status_code=201)
def ingest_cache_stats(data: dict) -> dict:
    """
    Receive edge cache statistics from the experiment runner script.
    Expected: { "hits": int, "misses": int, "source": str }
    """
    hits   = int(data.get("hits", 0))
    misses = int(data.get("misses", 0))
    source = str(data.get("source", "experiment"))[:50]

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO cache_stats (hits, misses, total, source)
               VALUES (?, ?, ?, ?)""",
            (hits, misses, hits + misses, source),
        )
    return {"stored": True, "hits": hits, "misses": misses}
