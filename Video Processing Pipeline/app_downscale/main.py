"""
FastAPI Video Compression Service
==================================
Professional API for compressing videos from URL or local file.

Author: VidP Team
Version: 1.1.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from config.settings import Settings
from utils.logging_config import logger
from routes.compression_routes import router as compression_router
from routes.status_routes import router as status_router
from routes.test_routes import router as test_router
from routes.static_routes import router as static_router


#  Lifespan manager (replaces startup/shutdown events)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---------- Startup ----------
    logger.info(f"{Settings.API_TITLE} v{Settings.API_VERSION} started")
    logger.info(f"Storage directory: {Settings.BASE_DIR.absolute()}")
    
    # Create necessary directories
    Settings.BASE_DIR.mkdir(parents=True, exist_ok=True)
    Settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    Settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    Settings.COMPRESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create resolution subdirectories
    for resolution in Settings.SUPPORTED_RESOLUTIONS.keys():
        (Settings.COMPRESSED_DIR / resolution).mkdir(parents=True, exist_ok=True)
    
    logger.info("Available endpoints:")
    logger.info("- POST /api/compress/url - Compress from URL")
    logger.info("- POST /api/compress/local - Compress local file")
    logger.info("- POST /api/compress/upload - Upload and compress")
    logger.info("- GET /api/status/{job_id} - Check job status")
    logger.info("- GET /api/download/{job_id} - Download result")
    logger.info("- GET /video_storage/ - Access video files")

    yield  # App is running here

    # ---------- Shutdown ----------
    logger.info("Video Compression API shutting down")


# Create FastAPI app with lifespan
app = FastAPI(
    title=Settings.API_TITLE,
    description=Settings.API_DESCRIPTION,
    version=Settings.API_VERSION,
    docs_url=Settings.API_DOCS_URL,
    redoc_url=Settings.API_REDOC_URL,
    lifespan=lifespan,
    timeout=Settings.API_TIMEOUT
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
app.mount("/video_storage", StaticFiles(directory=str(Settings.BASE_DIR)), name="video_storage")

# Routers
app.include_router(compression_router)
app.include_router(status_router)
app.include_router(test_router)
app.include_router(static_router)


@app.get("/")
async def root():
    """API health check endpoint"""
    return {
        "service": Settings.API_TITLE,
        "status": "running",
        "version": Settings.API_VERSION,
        "features": [
            "Compress videos from URLs",
            "Compress local video files",
            "Upload and compress videos",
            "Multiple resolutions (240p to 1080p)",
            "Adjustable quality (CRF 18-30)"
        ],
        "endpoints": {
            "compress_url": "/api/compress/url",
            "compress_local": "/api/compress/local",
            "compress_upload": "/api/compress/upload",
            "status": "/api/status/{job_id}",
            "download": "/api/download/{job_id}",
            "cleanup": "/api/cleanup/{job_id}",
            "test": "/api/test/local",
            "video_storage": "/video_storage/{path}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8001) 
