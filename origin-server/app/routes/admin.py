"""
admin.py — Admin-only endpoints: video upload and job status polling.

These endpoints are intentionally separate from the public viewer endpoints
so we can add authentication here later without touching the viewer routes.

Endpoints:
  POST   /admin/upload           — Accept a video file upload
  GET    /admin/videos           — List all videos (including processing ones)
  GET    /admin/jobs/{job_id}    — Poll FFmpeg processing progress
  DELETE /admin/videos/{video_id} — Remove video and its files
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from app.database import get_connection
from app.models.schemas import JobStatus, UploadResponse
from app.services import ffmpeg_service, storage_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=1000),
) -> UploadResponse:
    """
    Accept a video file upload from the admin interface.

    1. Validates file type and size.
    2. Saves the raw file to uploads/ with a UUID filename.
    3. Creates DB records for the video and processing job.
    4. Kicks off FFmpeg transcoding in a background task.
    5. Returns immediately (202 Accepted) with video_id and job_id.

    The admin polls GET /admin/jobs/{job_id} to track progress.
    """
    # ── Validate file extension ────────────────────────────────────────────────
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. "
                   f"Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── Generate IDs and safe file path ───────────────────────────────────────
    video_id = str(uuid.uuid4())
    job_id   = str(uuid.uuid4())
    dest     = storage_service.get_upload_path(video_id, ext)

    # ── Stream file to disk, checking size along the way ──────────────────────
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    total_written = 0

    try:
        with open(dest, "wb") as f_out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB at a time
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_bytes:
                    # Clean up partial file before rejecting
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.",
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    # ── Insert DB records ──────────────────────────────────────────────────────
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO videos (video_id, title, description) VALUES (?, ?, ?)",
            (video_id, title.strip(), description.strip()),
        )
        conn.execute(
            """INSERT INTO processing_jobs (job_id, video_id, started_at)
               VALUES (?, ?, datetime('now'))""",
            (job_id, video_id),
        )

    # ── Start background transcoding ───────────────────────────────────────────
    background_tasks.add_task(ffmpeg_service.transcode_video, video_id, job_id, dest)

    return UploadResponse(
        video_id=video_id,
        job_id=job_id,
        message="Upload accepted. Processing has started.",
    )


@router.get("/videos")
def list_all_videos() -> list:
    """
    Return all videos including ones still processing or failed.
    The public GET /videos only returns ready videos.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str) -> JobStatus:
    """
    Poll the status of an FFmpeg processing job.
    The admin UI calls this every 3 seconds after uploading.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JobStatus(**dict(row))


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: str) -> None:
    """
    Delete a video and all its associated files.
    This is irreversible.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    if row["status"] == "processing":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a video that is currently being processed.",
        )

    # Remove files from disk
    storage_service.delete_video_files(video_id, "")  # extension unknown; deletes dir

    # Remove DB records (cascade deletes the job too)
    with get_connection() as conn:
        conn.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
