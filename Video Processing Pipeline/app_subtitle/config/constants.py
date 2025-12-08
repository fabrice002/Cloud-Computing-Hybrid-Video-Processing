"""Application constants"""

# Error Messages
ERROR_MESSAGES = {
    "file_too_large": "File size exceeds maximum allowed size",
    "unsupported_format": "Unsupported file format",
    "no_audio_track": "Video file has no audio track",
    "whisper_failed": "Failed to generate subtitles",
    "ffmpeg_failed": "Failed to process video",
    "service_not_ready": "Service not initialized"
}

# Processing Status
STATUS_MESSAGES = {
    "uploading": "Uploading video...",
    "extracting_audio": "Extracting audio track...",
    "transcribing": "Transcribing audio...",
    "generating_subtitles": "Generating subtitle file...",
    "embedding_subtitles": "Embedding subtitles into video...",
    "completed": "Processing completed successfully"
}

# Supported Languages (Whisper)
SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese"
}