"""
ffmpeg_service.py — Video transcoding using FFmpeg.

This module wraps FFmpeg subprocess calls.
All FFmpeg work runs in a thread-pool executor so it does not
block FastAPI's async event loop.

Workflow:
  1. Probe source file to get duration.
  2. Transcode each configured resolution to HLS format.
  3. Write a master HLS playlist linking all quality levels.
  4. Update the DB job and video records throughout.
"""
import asyncio
import json
import subprocess
import shutil
from pathlib import Path

from app.config import FFMPEG_BIN, SEGMENT_DURATION, RESOLUTIONS, PROCESSED_DIR
from app.database import get_connection


# ─── Public API ────────────────────────────────────────────────────────────────

async def transcode_video(video_id: str, job_id: str, source_path: Path) -> None:
    """
    Async entry point — offloads blocking FFmpeg work to a thread.
    Called by the FastAPI BackgroundTasks mechanism.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_ffmpeg_blocking, video_id, job_id, source_path)


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _run_ffmpeg_blocking(video_id: str, job_id: str, source_path: Path) -> None:
    """
    Blocking FFmpeg pipeline — runs in a worker thread.

    Steps:
      1. Create output directory.
      2. Probe duration.
      3. Transcode each resolution.
      4. Write master playlist.
      5. Update DB to 'ready' or 'failed'.
    """
    out_dir = PROCESSED_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    _update_job(job_id, "processing", 5)

    # ── Step 1: Probe duration ─────────────────────────────────────────────────
    duration_s = _probe_duration(source_path)

    # ── Step 2: Transcode each resolution ─────────────────────────────────────
    completed_variants = []  # list of (label, width, height, bitrate_kbps)

    for i, (label, width, height, bitrate_kbps) in enumerate(RESOLUTIONS):
        seg_pattern  = str(out_dir / f"seg_%05d_{label}.ts")
        playlist_out = str(out_dir / f"{label}.m3u8")

        cmd = [
            FFMPEG_BIN,
            "-y",                            # overwrite if exists
            "-i", str(source_path),          # input file
            "-vf", f"scale={width}:{height}",
            "-c:v", "libx264",
            "-preset", "fast",               # fast encode, reasonable quality
            "-crf", "23",                    # constant rate factor
            "-b:v", f"{bitrate_kbps}k",      # target video bitrate
            "-c:a", "aac",
            "-b:a", "128k",
            "-hls_time", str(SEGMENT_DURATION),
            "-hls_playlist_type", "vod",     # VOD: complete playlist written at end
            "-hls_segment_filename", seg_pattern,
            playlist_out,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # FFmpeg failed — record error and stop processing
            error_msg = result.stderr[-2000:]  # keep last 2000 chars
            _update_job(job_id, "failed", 0, error_msg)
            _update_video_status(video_id, "failed", None, [])
            return

        completed_variants.append((label, width, height, bitrate_kbps))

        # Update progress proportionally: 5% (probe) + 85% (encode) = 90% at end
        progress = 5 + int(((i + 1) / len(RESOLUTIONS)) * 85)
        _update_job(job_id, "processing", progress)

    # ── Step 3: Write master HLS playlist ─────────────────────────────────────
    master_path = out_dir / "master.m3u8"
    _write_master_playlist(master_path, completed_variants)

    # ── Step 4: Mark as complete ───────────────────────────────────────────────
    _update_job(job_id, "ready", 100)
    _update_video_status(
        video_id,
        status="ready",
        hls_path=str(out_dir),
        resolutions=[v[0] for v in completed_variants],
        duration_s=duration_s,
    )


def _probe_duration(source_path: Path) -> float | None:
    """
    Use ffprobe to extract video duration in seconds.
    Returns None if probing fails (non-fatal; duration stored as NULL).
    """
    probe_cmd = [
        FFMPEG_BIN.replace("ffmpeg", "ffprobe"),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(source_path),
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info.get("format", {}).get("duration", 0)) or None
    except Exception:
        pass
    return None


def _write_master_playlist(master_path: Path, variants: list) -> None:
    """
    Write an HLS master playlist referencing all quality-level playlists.
    Format follows HLS spec (RFC 8216).
    """
    with open(master_path, "w") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n\n")

        # Write lowest to highest bitrate for standard player compatibility
        for label, width, height, bitrate_kbps in sorted(variants, key=lambda v: v[3]):
            bandwidth = bitrate_kbps * 1000   # BANDWIDTH is in bits/s
            f.write(f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},"
                    f"RESOLUTION={width}x{height},"
                    f"NAME=\"{label}\"\n")
            f.write(f"{label}.m3u8\n")


# ─── DB helpers (internal) ─────────────────────────────────────────────────────

def _update_job(job_id: str, status: str, progress: int, error: str = None) -> None:
    """Update a processing job's status and progress in the DB."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE processing_jobs
               SET status=?, progress=?, error_msg=?,
                   finished_at = CASE WHEN ? IN ('ready','failed')
                                 THEN datetime('now') ELSE finished_at END
               WHERE job_id=?""",
            (status, progress, error, status, job_id),
        )


def _update_video_status(
    video_id: str,
    status: str,
    hls_path: str | None,
    resolutions: list,
    duration_s: float | None = None,
) -> None:
    """Update a video's status, resolutions, and duration after transcoding."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE videos
               SET status=?, hls_path=?, resolutions=?, duration_s=?
               WHERE video_id=?""",
            (status, hls_path, json.dumps(resolutions), duration_s, video_id),
        )
