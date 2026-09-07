"""FastAPI application for the Furniture Bill license server.

Run with:
    uvicorn app.main:app --reload

HTTPS must be terminated at the reverse proxy in production.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

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


@app.get("/")
def root():
    return {"service": "furniture-bill-license-server", "version": "1.0.0"}


@app.get("/health")
def health():
    """Safe public health check endpoint."""
    return {"status": "healthy", "service": "furniture-bill-license-server", "version": "1.0.0"}