# -*- coding: utf-8 -*-
# app_langscale/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.logging_config import setup_logging
from api.router import api_router
from config.settings import Settings
import sys

# Ensure UTF-8 encoding (Windows-safe)
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Setup logging
logger = setup_logging()


# Lifespan listener (startup & shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # -------- STARTUP --------
    logger.info(" Video Language Detection API starting up")
    logger.info("Service: VidP Team")
    logger.info(f"Version: {Settings.API_VERSION}")
    
    # Create directories
    Settings.BASE_DIR.mkdir(parents=True, exist_ok=True)
    Settings.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    Settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    Settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("API routes loaded successfully")
    logger.info("Available endpoints:")
    logger.info("- POST /api/detect - Detect from URL (async/sync)")
    logger.info("- POST /api/detect/local - Detect from local file (async/sync)")
    logger.info("- POST /api/detect/upload - Upload and detect (async/sync)")
    logger.info("- GET /api/status/{job_id} - Check job status")
    logger.info("- GET /api/languages - Get supported languages")
    logger.info("- GET /api/stats - Get API statistics")

    yield  # Application runs here

    # -------- SHUTDOWN --------
    logger.info(" Video Language Detection API shutting down")
    logger.info("Resources released successfully")


# FastAPI app with lifespan
app = FastAPI(
    title=Settings.API_TITLE,
    description=Settings.API_DESCRIPTION,
    version=Settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """API health check endpoint"""
    return {
        "service": Settings.API_TITLE,
        "status": "running",
        "version": Settings.API_VERSION,
        "endpoints": {
            "detect": {
                "url": "/api/detect",
                "method": "POST",
                "description": "Detect language from video URL (async/sync)"
            },
            "detect_local": {
                "url": "/api/detect/local",
                "method": "POST",
                "description": "Detect language from local file (async/sync)"
            },
            "detect_upload": {
                "url": "/api/detect/upload",
                "method": "POST",
                "description": "Upload video and detect language (async/sync)"
            },
            "status": "/api/status/{job_id}",
            "languages": "/api/languages",
            "cleanup": "/api/cleanup/{job_id}",
            "stats": "/api/stats",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8002)