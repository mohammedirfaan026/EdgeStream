"""
database.py — SQLite connection and schema initialisation.

Tables:
  videos           — video metadata (title, status, resolutions, etc.)
  processing_jobs  — FFmpeg job tracking (progress, errors)

Call init_db() once at server startup (done in main.py).
Use get_connection() anywhere you need a DB handle; it sets row_factory
so results come back as dict-like objects.
"""
import sqlite3
from app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    Return an open SQLite connection.
    row_factory = sqlite3.Row lets you access columns by name.
    WAL journal mode allows concurrent readers alongside a writer.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    Called once when the FastAPI application starts.
    """
    UPLOAD_DIR = DB_PATH.parent / "uploads"
    PROCESSED_DIR = DB_PATH.parent / "processed"
    STATIC_DIR = DB_PATH.parent / "static"

    # Ensure runtime directories exist
    for d in (UPLOAD_DIR, PROCESSED_DIR, STATIC_DIR):
        d.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            -- ── Videos table ────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS videos (
                video_id    TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT DEFAULT '',
                duration_s  REAL,
                -- JSON array stored as text, e.g. '["360p","480p","720p"]'
                resolutions TEXT DEFAULT '[]',
                -- processing | ready | failed
                status      TEXT DEFAULT 'processing',
                hls_path    TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            -- ── Processing jobs table ────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS processing_jobs (
                job_id      TEXT PRIMARY KEY,
                video_id    TEXT REFERENCES videos(video_id) ON DELETE CASCADE,
                -- queued | processing | ready | failed
                status      TEXT DEFAULT 'queued',
                progress    INTEGER DEFAULT 0,   -- 0–100
                error_msg   TEXT,
                started_at  TEXT DEFAULT (datetime('now')),
                finished_at TEXT
            );
        """)
