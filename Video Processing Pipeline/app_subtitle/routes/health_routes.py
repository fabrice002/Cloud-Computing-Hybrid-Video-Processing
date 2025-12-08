from fastapi import APIRouter
from datetime import datetime

from config.settings import Settings
from models.response_models import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=Settings.API_TITLE,
        timestamp=datetime.now(),
        version=Settings.API_VERSION,
        processor_ready=True
    )

@router.get("/info")
async def api_info():
    """Get API information."""
    return {
        "service": Settings.API_TITLE,
        "version": Settings.API_VERSION,
        "description": Settings.API_DESCRIPTION,
        "features": [
            "Automatic subtitle generation using Whisper AI",
            "Support for multiple languages",
            "Subtitle embedding into videos",
            "Multiple Whisper model sizes",
            "Preserves audio quality"
        ],
        "supported_formats": sorted(Settings.ALLOWED_EXTENSIONS),
        "whisper_models": Settings.WHISPER_MODELS
    }