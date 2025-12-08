# app_langscale/models/request_models.py
from pydantic import BaseModel, HttpUrl, Field

class LanguageDetectionRequest(BaseModel):
    """
    Request model for language detection
    
    Attributes:
        video_url: URL of the video to download and analyze
        duration: Duration in seconds to analyze (default: 30)
        test_all_languages: If True, test all supported languages
    """
    video_url: HttpUrl = Field(..., description="URL of the video to download")
    duration: int = Field(default=30, ge=5, le=120, description="Duration to analyze in seconds")
    test_all_languages: bool = Field(default=True, description="Test all 15 supported languages")


class LocalVideoDetectionRequest(BaseModel):
    """
    Request model for local video detection
    """
    video_path: str = Field(..., description="Chemin local vers la vidéo")
    duration: int = Field(default=30, ge=5, le=120)
    test_all_languages: bool = Field(default=True)