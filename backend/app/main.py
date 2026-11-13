"""FastAPI application composition."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(BACKEND_ENV_FILE, override=False)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import auth, catalog, chat, conversations, media, reviews
from app.db.database import engine, init_db
from app.schemas.common import HealthResponse
from app.core.media_limits import MediaUploadLimitMiddleware

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        if os.getenv("APP_ENV", "").lower() == "production":
            raise RuntimeError(
                "CORS_ORIGINS must list the deployed frontend origins in production."
            )
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    origins = [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    if not origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one frontend origin.")
    if os.getenv("APP_ENV", "").lower() == "production" and "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS cannot use '*' in production; list the exact frontend origins."
        )
    return origins


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Jenga Consultants Product Copilot", version="1.0.0", lifespan=lifespan)
app.add_middleware(MediaUploadLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(catalog.router)
app.include_router(catalog.legacy_router)
app.include_router(media.router)
app.include_router(conversations.router)
app.include_router(reviews.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc))


@app.get("/", response_model=HealthResponse, include_in_schema=False)
def root_health() -> HealthResponse:
    return health()


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def versioned_health() -> HealthResponse:
    return health()


@app.get("/ready", tags=["health"])
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ready"}


@app.get("/api/v1/ready", tags=["health"])
def versioned_ready() -> dict[str, str]:
    return ready()
