from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from models.enums import VideoSourceType, JobStatus

class CompressionStatus(BaseModel):
    """Response model for compression status"""
    job_id: str
    source_type: VideoSourceType
    status: JobStatus
    message: str
    output_path: Optional[str] = Field(
        None, 
        description="Absolute file system path to the compressed video"
    )
    video_url: Optional[str] = Field(
        None,
        description="HTTP URL to stream/play the video directly"
    )
    download_url: Optional[str] = Field(
        None,
        description="HTTP URL to download the compressed video"
    )
    metadata: Optional[Dict] = None
    async_mode: bool = Field(
        True, 
        description="Processing mode: True for async, False for sync"
    )

class CompressionResult(BaseModel):
    """Detailed compression result"""
    job_id: str
    status: JobStatus
    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    processing_time_seconds: float
    resolution: str
    output_path: str = Field(
        ...,
        description="Absolute file system path to the compressed video"
    )
    video_url: str = Field(
        ...,
        description="HTTP URL to stream/play the video directly"
    )
    download_url: str = Field(
        ...,
        description="HTTP URL to download the compressed video"
    )
    metadata: Dict[str, Any]

class CleanupResponse(BaseModel):
    """Response for cleanup operation"""
    job_id: str
    message: str
    files_deleted: list[str]

class APIInfo(BaseModel):
    """API information response"""
    service: str
    status: str
    version: str
    features: list[str]
    endpoints: Dict[str, str]

class TestResult(BaseModel):
    """Test endpoint response"""
    status: str
    job_id: str
    message: str
    result: Optional[Dict[str, Any]] = None