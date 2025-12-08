# -*- coding: utf-8 -*-
# app_subtitle/main.py
"""
FastAPI application for automatic video subtitle generation and embedding.

This application provides endpoints to:
- Upload videos for subtitle generation
- Generate subtitles using Whisper AI
- Embed subtitles into videos while preserving audio
- Download processed videos
"""



from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config.settings import Settings
from utils.logging_config import logger
from routes.subtitle_routes import router as subtitle_router
from routes.health_routes import router as health_router
from services.video_processor import VideoProcessor
import sys

# Ensure UTF-8 encoding (Windows-safe)
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Global processor instance
processor: VideoProcessor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global processor
    
    # Startup
    logger.info(f"Starting {Settings.API_TITLE} v{Settings.API_VERSION}")
    logger.info(f"Output directory: {Settings.OUTPUT_DIR.absolute()}")
    logger.info(f"Temp directory: {Settings.TEMP_DIR.absolute()}")
    
    # Initialize processor
    processor = VideoProcessor()
    logger.info("Video processor initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    if processor:
        processor.cleanup()

# Create FastAPI app
app = FastAPI(
    title=Settings.API_TITLE,
    description=Settings.API_DESCRIPTION,
    version=Settings.API_VERSION,
    docs_url=Settings.API_DOCS_URL,
    redoc_url=Settings.API_REDOC_URL,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(subtitle_router)
app.include_router(health_router)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": Settings.API_TITLE,
        "version": Settings.API_VERSION,
        "status": "running",
        "endpoints": {
            "generate_subtitles": "/api/generate-subtitles/",
            "health": "/api/health",
            "info": "/api/info",
            "docs": Settings.API_DOCS_URL
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        app, 
        port=8003,
        log_level="info"
    )