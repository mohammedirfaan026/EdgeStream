"""
generate_synthetic_data.py -- Populate edgestream.db with simulated playback data.

Use this for testing the machine learning training pipeline (train.py, evaluate.py)
and verifying the dashboard charts prior to running physical LAN experiments.

Generates:
  - 10 Normal sessions: buffer steady at 15-30s, low bitrate variation, no buffering.
  - 8 Throttled sessions (2 Mbps): buffer fluctuates 3-10s, occasional buffering.
  - 6 Severely throttled sessions (1 Mbps): buffer drops to 0-2s, repeated buffering.

Usage (from ai-monitoring-server/ directory):
    python scripts/generate_synthetic_data.py
"""
import sys
import uuid
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.database import get_connection, init_db


def main():
    print("Generating simulated playback dataset for EdgeStream AI...")
    init_db()

    conn = get_connection()
    # Optional: clear existing test data
    conn.execute("DELETE FROM playback_events")
    conn.execute("DELETE FROM buffering_events")
    conn.execute("DELETE FROM predictions")
    conn.execute("DELETE FROM sessions")
    conn.commit()

    total_events = 0
    total_buf_events = 0

    base_time = datetime.now() - timedelta(hours=3)

    # 1. Normal sessions (10 sessions, 60 ticks each = 5 minutes of streaming each)
    for s_idx in range(10):
        sid = f"synth-norm-{s_idx:02d}-{uuid.uuid4().hex[:6]}"
        vid = "demo-video-1"
        start = base_time + timedelta(minutes=s_idx * 15)
        conn.execute("INSERT INTO sessions (session_id, video_id, started_at, last_seen, is_active) VALUES (?, ?, ?, ?, 0)",
                     (sid, vid, start.isoformat(), (start + timedelta(minutes=5)).isoformat()))

        buffer_s = 20.0
        for tick in range(60):
            t = start + timedelta(seconds=tick * 5)
            # Normal drift around 18-28 seconds
            buffer_s = max(15.0, min(30.0, buffer_s + random.uniform(-1.0, 1.2)))
            bitrate = random.choice([2500, 2800])
            dl_speed = random.uniform(8000, 15000)
            dl_time = random.uniform(150, 350)

            conn.execute("""
                INSERT INTO playback_events
                (session_id, recorded_at, playback_time_s, buffer_s, bitrate_kbps, dl_speed_kbps, dl_time_ms, is_buffering, quality_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 2)
            """, (sid, t.isoformat(), tick * 5.0, round(buffer_s, 2), bitrate, round(dl_speed, 1), round(dl_time, 1)))
            total_events += 1

    # 2. Moderately throttled sessions (8 sessions)
    for s_idx in range(8):
        sid = f"synth-mod-{s_idx:02d}-{uuid.uuid4().hex[:6]}"
        vid = "demo-video-1"
        start = base_time + timedelta(minutes=160 + s_idx * 12)
        conn.execute("INSERT INTO sessions (session_id, video_id, started_at, last_seen, is_active) VALUES (?, ?, ?, ?, 0)",
                     (sid, vid, start.isoformat(), (start + timedelta(minutes=5)).isoformat()))

        buffer_s = 12.0
        is_buf = False
        for tick in range(60):
            t = start + timedelta(seconds=tick * 5)
            # Throttle pressure
            if tick > 15 and tick < 35:
                buffer_s = max(0.0, buffer_s - random.uniform(0.8, 1.8))
            else:
                buffer_s = max(2.0, min(14.0, buffer_s + random.uniform(-0.5, 0.8)))

            if buffer_s <= 0.5:
                if not is_buf:
                    conn.execute("INSERT INTO buffering_events (session_id, occurred_at, buffer_before_s) VALUES (?, ?, ?)",
                                 (sid, t.isoformat(), round(buffer_s, 2)))
                    total_buf_events += 1
                is_buf = True
            else:
                is_buf = False

            bitrate = 1400 if buffer_s > 4 else 800
            dl_speed = random.uniform(1800, 2400)
            dl_time = random.uniform(900, 1600)

            conn.execute("""
                INSERT INTO playback_events
                (session_id, recorded_at, playback_time_s, buffer_s, bitrate_kbps, dl_speed_kbps, dl_time_ms, is_buffering, quality_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sid, t.isoformat(), tick * 5.0, round(buffer_s, 2), bitrate, round(dl_speed, 1), round(dl_time, 1), 1 if is_buf else 0, 1 if bitrate == 1400 else 0))
            total_events += 1

    # 3. Severely throttled sessions (6 sessions)
    for s_idx in range(6):
        sid = f"synth-sev-{s_idx:02d}-{uuid.uuid4().hex[:6]}"
        vid = "demo-video-1"
        start = base_time + timedelta(minutes=260 + s_idx * 10)
        conn.execute("INSERT INTO sessions (session_id, video_id, started_at, last_seen, is_active) VALUES (?, ?, ?, ?, 0)",
                     (sid, vid, start.isoformat(), (start + timedelta(minutes=5)).isoformat()))

        buffer_s = 8.0
        is_buf = False
        for tick in range(60):
            t = start + timedelta(seconds=tick * 5)
            if tick > 8:
                buffer_s = max(0.0, buffer_s - random.uniform(0.7, 1.6))
            else:
                buffer_s = min(8.0, buffer_s + random.uniform(-0.2, 0.5))

            if buffer_s <= 0.4:
                if not is_buf:
                    conn.execute("INSERT INTO buffering_events (session_id, occurred_at, buffer_before_s) VALUES (?, ?, ?)",
                                 (sid, t.isoformat(), round(buffer_s, 2)))
                    total_buf_events += 1
                is_buf = True
            else:
                is_buf = False

            bitrate = 800
            dl_speed = random.uniform(700, 1100)
            dl_time = random.uniform(2200, 4100)

            conn.execute("""
                INSERT INTO playback_events
                (session_id, recorded_at, playback_time_s, buffer_s, bitrate_kbps, dl_speed_kbps, dl_time_ms, is_buffering, quality_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (sid, t.isoformat(), tick * 5.0, round(buffer_s, 2), bitrate, round(dl_speed, 1), round(dl_time, 1), 1 if is_buf else 0))
            total_events += 1

    conn.commit()
    conn.close()

    print(f"Dataset generated successfully!")
    print(f"  Sessions:         24")
    print(f"  Playback events:  {total_events}")
    print(f"  Buffering events: {total_buf_events}")
    print("\nYou can now run:")
    print("  python scripts/train.py")
    print("  python scripts/export_data.py")
    print("  python ../experiments/ai_evaluation/evaluate.py")


if __name__ == "__main__":
    main()
