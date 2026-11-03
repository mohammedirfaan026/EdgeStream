"""
export_data.py -- Export playback events from SQLite to CSV for analysis.

This script produces:
  - playback_events.csv   -- all raw telemetry rows
  - labeled_events.csv    -- telemetry with look-ahead labels (same as train.py uses)
  - sessions_summary.csv  -- one row per session with aggregated stats

Usage (from ai-monitoring-server/ directory):
    python scripts/export_data.py

Output files go to the data/ directory.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pandas as pd
from app.config import DB_PATH, DATA_DIR
from app.prediction.labeler import label_events_from_db


def main():
    print("Exporting EdgeStream AI data to CSV...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    # -- Raw playback events ----------------------------------------------------
    df_events = pd.read_sql_query(
        "SELECT * FROM playback_events ORDER BY session_id, recorded_at",
        conn,
    )
    out1 = DATA_DIR / "playback_events.csv"
    df_events.to_csv(out1, index=False)
    print(f"  Saved {len(df_events)} rows -> {out1}")

    # -- Buffering events -------------------------------------------------------
    df_buf = pd.read_sql_query("SELECT * FROM buffering_events", conn)
    out2 = DATA_DIR / "buffering_events.csv"
    df_buf.to_csv(out2, index=False)
    print(f"  Saved {len(df_buf)} rows -> {out2}")

    # -- Sessions summary -------------------------------------------------------
    df_sessions = pd.read_sql_query("""
        SELECT s.session_id, s.video_id, s.started_at, s.last_seen,
               COUNT(e.id) as event_count,
               AVG(e.buffer_s) as avg_buffer_s,
               SUM(e.is_buffering) as buffering_ticks,
               (SELECT COUNT(*) FROM buffering_events b WHERE b.session_id = s.session_id)
               as buffering_events
        FROM sessions s
        LEFT JOIN playback_events e ON e.session_id = s.session_id
        GROUP BY s.session_id
        ORDER BY s.started_at
    """, conn)
    out3 = DATA_DIR / "sessions_summary.csv"
    df_sessions.to_csv(out3, index=False)
    print(f"  Saved {len(df_sessions)} rows -> {out3}")

    # -- Labeled events (for inspection) ---------------------------------------
    df_labeled = label_events_from_db()
    if not df_labeled.empty:
        out4 = DATA_DIR / "labeled_events.csv"
        df_labeled.to_csv(out4, index=False)
        print(f"  Saved {len(df_labeled)} rows -> {out4}")
        print(f"  Label distribution: {df_labeled['label'].value_counts().to_dict()}")

    conn.close()
    print("\nExport complete.")


if __name__ == "__main__":
    main()
