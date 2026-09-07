"""FastAPI application for the Furniture Bill license server.

Run with:
    uvicorn app.main:app --reload

HTTPS must be terminated at the reverse proxy in production.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models.database import init_db
from app.routes import activation_router, admin_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("License server started (env=%s)", get_settings().environment)
    if not get_settings().private_signing_key:
        logger.warning("PRIVATE_SIGNING_KEY is not set — license signing will fail until configured.")
    yield
    logger.info("License server shut down")


app = FastAPI(
    title="Furniture Bill License Server",
    version="1.0.0",
    description="Commercial lifetime-license activation for the Furniture Bill desktop app.",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# CORS is not needed for a desktop client, but harmless for the admin web UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "PUT"],
    allow_headers=["*"],
)

app.include_router(activation_router)
app.include_router(admin_router)

from fastapi.responses import RedirectResponse

ADMIN_STATIC_DIR = Path(__file__).resolve().parent.parent / "admin_web" / "static"
if ADMIN_STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    
    @app.get("/admin", include_in_schema=False)
    def redirect_admin_slash():
        return RedirectResponse(url="/admin/")

    @app.get("/style.css", include_in_schema=False)
    def serve_root_style_css():
        from fastapi.responses import FileResponse
        return FileResponse(str(ADMIN_STATIC_DIR / "style.css"), media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    def serve_root_app_js():
        from fastapi.responses import FileResponse
        return FileResponse(str(ADMIN_STATIC_DIR / "app.js"), media_type="application/javascript")
        
    app.mount("/admin", StaticFiles(directory=str(ADMIN_STATIC_DIR), html=True), name="admin_ui")


@app.get("/")
def root():
    return {"service": "furniture-bill-license-server", "version": "1.0.0"}


@app.get("/health")
def health():
    """Safe public health check endpoint."""
    return {"status": "healthy", "service": "furniture-bill-license-server", "version": "1.0.0"}