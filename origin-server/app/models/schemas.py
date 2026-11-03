"""
schemas.py — Pydantic models for request validation and response serialisation.

These are the data shapes that travel over the API.
Pydantic validates incoming data automatically when used as FastAPI parameters.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class VideoSummary(BaseModel):
    """Returned by GET /videos — basic info without HLS path details."""
    video_id:    str
    title:       str
    description: str
    duration_s:  Optional[float]
    resolutions: List[str]
    status:      str
    created_at:  str


class VideoDetail(VideoSummary):
    """Returned by GET /videos/{video_id} — includes HLS path."""
    hls_path: Optional[str]


class UploadResponse(BaseModel):
    """Returned immediately after POST /admin/upload (202 Accepted)."""
    video_id: str
    job_id:   str
    message:  str


class JobStatus(BaseModel):
    """Returned by GET /admin/jobs/{job_id}."""
    job_id:      str
    video_id:    str
    status:      str                    # queued | processing | ready | failed
    progress:    int = Field(ge=0, le=100)
    error_msg:   Optional[str] = None
    started_at:  Optional[str] = None
    finished_at: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error shape."""
    detail: str
