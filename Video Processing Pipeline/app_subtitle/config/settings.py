import os
from pathlib import Path
from typing import List, Set

class Settings:
    """Application settings and configuration"""
    
    # API Configuration
    API_TITLE = "Video Subtitle Generator API"
    API_DESCRIPTION = "Automatic subtitle generation and embedding for videos"
    API_VERSION = "1.0.0"
    API_DOCS_URL = "/docs"
    API_REDOC_URL = "/redoc"
    
    # File System Configuration
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "output_videos"
    TEMP_DIR = BASE_DIR / "temp"
    
    # Whisper Model Configuration
    WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
    DEFAULT_MODEL = "base"
    
    # Video Processing Configuration
    ALLOWED_EXTENSIONS: Set[str] = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
    MAX_FILE_SIZE_MB = 500
    
    # FFmpeg Configuration
    FFMPEG_PRESET = "medium"
    FFMPEG_CRF = "23"
    AUDIO_CODEC = "aac"
    VIDEO_CODEC = "libx264"
    
    # Subtitle Configuration
    SRT_TIMESTAMP_FORMAT = "HH:MM:SS,mmm"
    
    @classmethod
    def init_directories(cls):
        """Create required directories"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Initialize directories
Settings.init_directories()