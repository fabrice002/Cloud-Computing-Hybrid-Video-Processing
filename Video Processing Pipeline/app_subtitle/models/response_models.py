from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    timestamp: datetime
    version: str
    processor_ready: bool

class ProcessingResult(BaseModel):
    """Result of subtitle processing."""
    success: bool
    message: str
    video_filename: Optional[str] = None
    subtitle_filename: Optional[str] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str
    timestamp: datetime