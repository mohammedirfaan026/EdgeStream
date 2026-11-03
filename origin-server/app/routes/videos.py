"""
videos.py — Public viewer endpoints and HLS file serving.

These endpoints are used by:
  - The viewer frontend (to list available videos).
  - The edge server (Nginx proxies all /hls/ requests here on cache miss).
  - hls.js (to fetch playlists and segments).

Endpoints:
  GET /videos                         — List all ready-to-play videos
  GET /videos/{video_id}              — Single video metadata
  GET /hls/{video_id}/master.m3u8     — Master HLS playlist
  GET /hls/{video_id}/{filename}      — Quality playlist or .ts segment
  GET /health                         — Server health check
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.database import get_connection
from app.services.storage_service import get_hls_file

router = APIRouter(tags=["videos"])


# ─── Health check ──────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    """Simple liveness probe — used by Nginx and monitoring."""
    return {"status": "ok", "server": "origin"}


# ─── Video catalogue ──────────────────────────────────────────────────────────

@router.get("/videos")
def list_videos() -> list:
    """
    Return a list of all videos whose status is 'ready'.
    Used by the viewer index page to populate the catalogue.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = 'ready' ORDER BY created_at DESC"
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        # Parse resolutions from JSON string to Python list
        try:
            d["resolutions"] = json.loads(d.get("resolutions") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["resolutions"] = []
        result.append(d)

    return result


@router.get("/videos/{video_id}")
def get_video(video_id: str) -> dict:
    """Return full metadata for a single video."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    d = dict(row)
    try:
        d["resolutions"] = json.loads(d.get("resolutions") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["resolutions"] = []
    return d


# ─── HLS file serving ─────────────────────────────────────────────────────────

@router.get("/hls/{video_id}/master.m3u8")
def serve_master_playlist(video_id: str):
    """
    Serve the HLS master playlist.

    Cache-Control: no-store — the edge server must NOT cache this.
    The master playlist changes as processing completes, and hls.js
    re-fetches it occasionally to detect quality changes.
    """
    path = get_hls_file(video_id, "master.m3u8")
    if path is None:
        raise HTTPException(status_code=404, detail="Master playlist not found. "
                            "Video may still be processing.")

    return FileResponse(
        path,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/hls/{video_id}/{filename}")
def serve_hls_file(video_id: str, filename: str):
    """
    Serve an HLS quality playlist (.m3u8) or media segment (.ts).

    Security: get_hls_file() rejects filenames containing '..' or
    path separators, preventing directory traversal.

    Cache-Control headers:
      .m3u8 quality playlists → cache for 1 hour (stable after processing)
      .ts   segments          → cache for 24 hours (immutable content)
    """
    # Only allow .m3u8 and .ts files
    if not (filename.endswith(".m3u8") or filename.endswith(".ts")):
        raise HTTPException(status_code=400, detail="Only .m3u8 and .ts files are served here.")

    path = get_hls_file(video_id, filename)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found for video '{video_id}'.",
        )

    if filename.endswith(".m3u8"):
        media_type = "application/vnd.apple.mpegurl"
        cache = "public, max-age=3600"          # 1 hour
    else:
        media_type = "video/MP2T"
        cache = "public, max-age=86400"         # 24 hours

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": cache,
            "Access-Control-Allow-Origin": "*",
        },
    )
