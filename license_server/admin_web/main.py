"""Admin web tool: a single-page UI over the license server admin API.

Run (from the license_server directory):
    uvicorn admin_web.main:app --host 0.0.0.0 --port 8080

Serving this tool is optional — if you don't need a browser UI, the JSON API
is fully sufficient on its own.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.models.database import init_db
from app.routes import activation_router, admin_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Furniture Bill License Admin",
    description="Remote license management for Furniture Bill.",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(admin_router)
app.include_router(activation_router)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="admin_ui")