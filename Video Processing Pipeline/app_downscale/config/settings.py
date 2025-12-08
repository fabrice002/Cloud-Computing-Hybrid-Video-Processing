import os
from pathlib import Path
from typing import List, Dict, Any

class Settings:
    """Application settings and configuration"""
    
    # API Configuration
    API_TITLE = "Video Compression API"
    API_DESCRIPTION = "Professional video compression service supporting URLs, local files, and uploads"
    API_VERSION = "1.1.0"
    API_DOCS_URL = "/docs"
    API_REDOC_URL = "/redoc"
    API_TIMEOUT   = 600
    
    # Storage Configuration
    BASE_DIR = Path("video_storage")
    DOWNLOADS_DIR = BASE_DIR / "downloads"
    COMPRESSED_DIR = BASE_DIR / "compressed"
    UPLOADS_DIR = BASE_DIR / "uploads"
    
    # Video Processing Configuration
    SUPPORTED_RESOLUTIONS = {
        "1080p": 1080,
        "720p": 720,
        "480p": 480,
        "360p": 360,
        "240p": 240
    }
    
    DEFAULT_RESOLUTION = "360p"
    DEFAULT_CRF_VALUE = 28
    MIN_CRF_VALUE = 18
    MAX_CRF_VALUE = 30
    
    # Encoding Configuration
    ENCODING_PRESET = "medium"
    AUDIO_BITRATE = "96k"
    AUDIO_CODEC = "aac"
    VIDEO_CODEC = "libx264"
    THREADS = 4
    
    # HTTP Configuration
    DOWNLOAD_TIMEOUT = 300.0
    MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1GB
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    
    # Logging
    LOG_FILE = "video_api.log"
    LOG_LEVEL = "INFO"
    
    @classmethod
    def init_directories(cls):
        """Create required directories"""
        cls.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        cls.COMPRESSED_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize directories
Settings.init_directories()