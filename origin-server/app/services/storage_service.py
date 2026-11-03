"""
storage_service.py — File path helpers and cleanup utilities.

Centralises all path construction so nothing else needs to know
the internal layout of the uploads/ and processed/ directories.
"""
import shutil
from pathlib import Path
from app.config import UPLOAD_DIR, PROCESSED_DIR


def get_upload_path(video_id: str, extension: str) -> Path:
    """Return the path where a raw uploaded file should be saved."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR / f"{video_id}{extension}"


def get_hls_dir(video_id: str) -> Path:
    """Return the directory that holds all HLS output for a video."""
    return PROCESSED_DIR / video_id


def get_hls_file(video_id: str, filename: str) -> Path | None:
    """
    Return the full path to an HLS file if it exists, else None.
    Validates that filename stays inside the video's HLS directory
    (prevents path traversal attacks).
    """
    # Reject any filename containing path separators or parent references
    if ".." in filename or "/" in filename or "\\" in filename:
        return None

    path = PROCESSED_DIR / video_id / filename
    if path.exists():
        return path
    return None


def delete_video_files(video_id: str, extension: str) -> None:
    """
    Remove all files for a video (upload + processed directory).
    Called when an admin deletes a video via the API.
    """
    # Remove raw upload
    upload = get_upload_path(video_id, extension)
    upload.unlink(missing_ok=True)

    # Remove entire HLS output directory
    hls_dir = get_hls_dir(video_id)
    if hls_dir.exists():
        shutil.rmtree(hls_dir)
