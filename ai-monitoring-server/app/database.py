"""
database.py — SQLite connection and schema initialisation for the AI server.

Tables:
  sessions         — one row per browser playback session
  playback_events  — one row per telemetry POST (5-second intervals)
  buffering_events — one row per detected buffering episode
  predictions      — one row per AI model inference
  cache_stats      — periodic edge cache hit/miss counts (posted by experiment script)
"""
import sqlite3
from app.config import DB_PATH, DATA_DIR


def get_connection() -> sqlite3.Connection:
    """
    Return an open SQLite connection with row_factory for dict-like access.
    WAL mode allows simultaneous reads from the dashboard while metrics are ingested.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they do not exist. Called once at server startup."""
    # Ensure runtime directories exist
    for d in (DATA_DIR, DB_PATH.parent / "models"):
        d.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            -- ── Sessions ────────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                video_id   TEXT,
                started_at TEXT DEFAULT (datetime('now')),
                last_seen  TEXT DEFAULT (datetime('now')),
                is_active  INTEGER DEFAULT 1   -- 0 = ended
            );

            -- ── Playback events (raw telemetry from browser) ─────────────────
            CREATE TABLE IF NOT EXISTS playback_events (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT REFERENCES sessions(session_id),
                recorded_at       TEXT DEFAULT (datetime('now')),
                playback_time_s   REAL,
                buffer_s          REAL,
                bitrate_kbps      REAL,
                dl_speed_kbps     REAL,
                dl_time_ms        REAL,
                is_buffering      INTEGER DEFAULT 0,
                quality_level     INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_events_session
                ON playback_events (session_id, recorded_at);

            -- ── Buffering events ──────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS buffering_events (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT REFERENCES sessions(session_id),
                occurred_at      TEXT DEFAULT (datetime('now')),
                buffer_before_s  REAL    -- buffer level just before buffering started
            );

            -- ── AI model predictions ──────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS predictions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT REFERENCES sessions(session_id),
                predicted_at    TEXT DEFAULT (datetime('now')),
                risk_score      REAL,
                predicted_label INTEGER,   -- 0 = no risk, 1 = high risk
                actual_label    INTEGER,   -- filled in retrospectively during eval
                model_version   TEXT,
                features_json   TEXT       -- JSON snapshot of input features
            );

            -- ── Edge cache statistics (populated by experiment script) ─────────
            CREATE TABLE IF NOT EXISTS cache_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT DEFAULT (datetime('now')),
                hits        INTEGER DEFAULT 0,
                misses      INTEGER DEFAULT 0,
                total       INTEGER DEFAULT 0,
                source      TEXT DEFAULT 'experiment'  -- 'experiment' or 'nginx-log'
            );
        """)
