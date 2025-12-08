"""Application constants"""

# API Endpoints
ENDPOINTS = {
    "root": "/",
    "compress_url": "/api/compress/url",
    "compress_local": "/api/compress/local",
    "compress_upload": "/api/compress/upload",
    "status": "/api/status/{job_id}",
    "download": "/api/download/{job_id}",
    "cleanup": "/api/cleanup/{job_id}",
    "test": "/api/test/local"
}

# Error Messages
ERROR_MESSAGES = {
    "job_not_found": "Job not found",
    "file_not_found": "File not found",
    "unsupported_format": "Unsupported file format",
    "download_failed": "Failed to download video",
    "compression_failed": "Compression failed",
    "invalid_crf": "CRF value must be between 18 and 30"
}

# Status Messages
STATUS_MESSAGES = {
    "pending": "Job queued for processing",
    "processing": "Processing video...",
    "completed": "Processing completed successfully",
    "failed": "Processing failed"
}