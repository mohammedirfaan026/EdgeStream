"""
labeler.py — Creates training labels from collected playback events.

Label definition:
  For each observation at time T in session S:
    Look at all events in session S from T+epsilon to T+LOOKAHEAD_SECONDS.
    If any of those events has is_buffering=True → label = 1 (buffering will occur).
    Otherwise → label = 0 (no buffering in the look-ahead window).

This labeling MUST be done only for training data, NOT at inference time.
At inference time we predict BEFORE we know whether buffering will occur.

Data leakage note:
  The label (future buffering) must never become an input feature.
  Only the features in FEATURE_NAMES are used for prediction.
"""
import sqlite3
import pandas as pd
from pathlib import Path
from app.config import DB_PATH, LOOKAHEAD_SECONDS


def label_events_from_db() -> pd.DataFrame:
    """
    Load all playback events from the DB, compute features, and attach labels.
    Returns a DataFrame ready for train/test split and model training.
    """
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(
        """
        SELECT
            session_id,
            recorded_at,
            playback_time_s,
            buffer_s,
            bitrate_kbps,
            dl_speed_kbps,
            dl_time_ms,
            is_buffering,
            quality_level
        FROM playback_events
        ORDER BY session_id, recorded_at
        """,
        conn,
    )
    conn.close()

    if df.empty:
        return df

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])

    # ── Compute buffer_trend per session ──────────────────────────────────────
    df = df.sort_values(["session_id", "recorded_at"])
    df["buffer_trend"] = (
        df.groupby("session_id")["buffer_s"]
        .diff()
        .fillna(0)
    )

    # ── Attach look-ahead label ───────────────────────────────────────────────
    labels = []
    for idx, row in df.iterrows():
        t_start = row["recorded_at"]
        t_end   = t_start + pd.Timedelta(seconds=LOOKAHEAD_SECONDS)

        future = df[
            (df["session_id"] == row["session_id"]) &
            (df["recorded_at"] > t_start) &
            (df["recorded_at"] <= t_end)
        ]

        labels.append(1 if future["is_buffering"].any() else 0)

    df["label"] = labels
    return df
