"""
event_processor.py — Detects and records buffering events from incoming telemetry.

A buffering event is recorded when:
  - The incoming metric has is_buffering=True AND
  - The previous metric for the same session had is_buffering=False
  (i.e., we record the START of each buffering episode, not every frame)

This avoids flooding the buffering_events table when buffering persists
for several telemetry intervals.
"""
from app.database import get_connection


# Cache the last known is_buffering state per session in memory.
# This is lost on server restart, but that's acceptable for a prototype.
_last_buffering_state: dict[str, bool] = {}


def process_buffering(session_id: str, is_buffering: bool, buffer_s: float) -> bool:
    """
    Check whether a new buffering episode has started for this session.
    Records the event in the DB if so.

    Returns True if a new buffering event was recorded, False otherwise.
    """
    was_buffering = _last_buffering_state.get(session_id, False)
    _last_buffering_state[session_id] = is_buffering

    if is_buffering and not was_buffering:
        # New buffering episode started
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO buffering_events (session_id, buffer_before_s)
                   VALUES (?, ?)""",
                (session_id, buffer_s),
            )
        return True

    return False


def get_session_buffering_count(session_id: str) -> int:
    """Return the total number of buffering events for a session."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM buffering_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row["cnt"] if row else 0
