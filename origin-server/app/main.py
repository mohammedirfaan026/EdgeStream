"""
main.py — FastAPI application entry point for the Origin Server.

Responsibilities:
  - Create the FastAPI app with CORS enabled.
  - Register all routers (admin, videos).
  - Mount static files (admin UI + viewer frontend).
  - Initialise the SQLite database on startup.
  - Provide a root redirect for convenience.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, STATIC_DIR
from app.database import init_db
from app.routes import admin as admin_router
from app.routes import videos as videos_router

# ─── Application instance ─────────────────────────────────────────────────────
app = FastAPI(
    title="EdgeStream AI — Origin Server",
    description="Video upload, transcoding, and HLS delivery.",
    version="1.0.0",
    docs_url="/api/docs",      # Swagger UI at /api/docs
    redoc_url="/api/redoc",
)

# ─── CORS — allow browsers from any LAN machine to access this server ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,    # ["*"] during LAN prototype
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """Initialise the database and ensure required directories exist."""
    init_db()


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(admin_router.router)
app.include_router(videos_router.router)


# ─── Static files ─────────────────────────────────────────────────────────────
# Serves:
#   /static/admin.html          — Admin upload interface
#   /static/viewer/index.html   — Video catalogue (viewer)
#   /static/viewer/player.html  — Video player (viewer)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    """Redirect the root URL to the admin interface."""
    return RedirectResponse(url="/static/admin.html")
