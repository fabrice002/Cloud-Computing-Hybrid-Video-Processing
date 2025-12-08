# app_langscale/config/settings.py

from pathlib import Path

class Settings:
    # API Configuration
    API_TITLE = "Video Language Detection API"
    API_VERSION = "1.1.0"
    API_DESCRIPTION = "Professional API for detecting spoken languages in videos"
    
    # File upload settings
    ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
    
    # Directories
    BASE_DIR = Path("language_detection_storage")
    VIDEOS_DIR = BASE_DIR / "videos"
    AUDIO_DIR = BASE_DIR / "audio"
    RESULTS_DIR = BASE_DIR / "results"
    
    # Detection settings
    DEFAULT_DURATION = 30  # seconds
    DEFAULT_TEST_ALL_LANGUAGES = True
    
    # Timeouts
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    PROCESSING_TIMEOUT = 600  # 10 minutes