"""
main.py — FastAPI application entry point for the AI & Monitoring Server.

Startup sequence:
  1. Initialise SQLite database.
  2. Attempt to load the trained ML model (falls back to baseline if not found).
  3. Register all API routers.
  4. Mount the static directory for the dashboard HTML/CSS/JS.
  5. Mark sessions inactive if they haven't sent data in 60 seconds
     (background cleanup task).

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8001
"""
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, STATIC_DIR
from app.database import get_connection, init_db
from app.prediction import model as model_module
from app.routes import dashboard as dashboard_router
from app.routes import metrics as metrics_router
from app.routes import predict as predict_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="EdgeStream AI — Monitoring & Prediction Server",
    description="Telemetry ingestion, buffering prediction, and monitoring dashboard.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    init_db()
    loaded = model_module.load_model()
    if loaded:
        logger.info("Prediction model loaded — using ML model.")
    else:
        logger.info("No trained model found — using 2-second buffer baseline.")

    # Start background session cleanup
    asyncio.create_task(_session_cleanup_loop())


async def _session_cleanup_loop():
    """
    Mark sessions inactive if they haven't sent data in 90 seconds.
    Runs every 30 seconds in the background.
    """
    while True:
        await asyncio.sleep(30)
        try:
            with get_connection() as conn:
                conn.execute(
                    """UPDATE sessions SET is_active = 0
                       WHERE is_active = 1
                       AND last_seen < datetime('now', '-90 seconds')"""
                )
        except Exception as exc:
            logger.warning("Session cleanup error: %s", exc)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(metrics_router.router)
app.include_router(predict_router.router)
app.include_router(dashboard_router.router)


# ── Static files ──────────────────────────────────────────────────────────────
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Health check and root ──────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "server": "ai-monitoring"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard")
