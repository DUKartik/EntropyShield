"""
main.py
EntropyShield / VeriDoc API — application entry point.

Responsibilities (only):
  - Create the FastAPI app instance
  - Register middleware (CORS, static files)
  - Wire up all routers
  - Run startup/shutdown lifecycle hooks
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.database_connector import init_mock_db
from utils.debug_logger import debug_router, get_logger

# Routers
from routers import admin, compliance, forensics

load_dotenv(override=True)

logger = get_logger()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Startup: initialising EntropyShield backend...")

    try:
        logger.info("Startup: initialising company database...")
        init_mock_db()
        logger.info("Startup: company database ready.")
    except Exception as e:
        logger.error(f"Startup: database init failed — {e}")

    # TruFor engine is lazy-loaded on first request to keep startup fast.

    yield
    logger.info("Shutdown: goodbye.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EntropyShield API",
    description="AI-powered Document Forensics & Compliance Automation",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow all localhost ports + the deployed frontend origin
# ---------------------------------------------------------------------------

_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "https://veridoc-frontend-808108840598.asia-south1.run.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.run\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files & routers
# ---------------------------------------------------------------------------

app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(forensics.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(debug_router, prefix="/api")


# ---------------------------------------------------------------------------
# Core health routes (too small to warrant a router)
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def read_root():
    return {"status": "online", "system": "EntropyShield Agentic Core"}


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
