from pydantic import BaseModel, Field
from typing import Optional
from config.settings import Settings

class SubtitleConfig(BaseModel):
    """Configuration for subtitle generation."""
    model_name: str = Field(
        default=Settings.DEFAULT_MODEL,
        description=f"Whisper model size. Options: {', '.join(Settings.WHISPER_MODELS)}"
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code for transcription (auto-detect if None). "
                   f"Supported: {', '.join(list(Settings.SUPPORTED_LANGUAGES.keys()))}"
    )

class UploadVideoRequest(BaseModel):
    """Request model for video upload with subtitle generation."""
    model_name: str = Settings.DEFAULT_MODEL
    language: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "model_name": "base",
                "language": "en"
            }
        }