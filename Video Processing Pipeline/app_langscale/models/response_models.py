# app_langscale/models/response_models.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from .enums import DetectionStatus

class LanguageDetectionResult(BaseModel):
    """
    Response model for language detection result
    
    Attributes:
        job_id: Unique identifier for the detection job
        status: Current status of the job
        message: Human-readable status message
        detected_language: Detected language information
        confidence_score: Confidence level of detection
        transcript_sample: Sample of transcribed text
        all_results: Results from all language tests
        metadata: Additional processing information
        async_mode: Processing mode (async/sync)
    """
    
    job_id: str
    status: DetectionStatus
    message: str
    detected_language: Optional[str] = None
    language_code: Optional[str] = None
    language_name: Optional[str] = None
    confidence_score: Optional[float] = None
    transcript_sample: Optional[str] = None
    all_results: Optional[List[Dict]] = None
    metadata: Optional[Dict] = None
    async_mode: bool = Field(default=True, description="True for async, False for sync")


class LanguageInfo(BaseModel):
    code: str
    display: str
    name: str
    
class SupportedLanguagesResponse(BaseModel):
    total: int
    languages: List[LanguageInfo]
    
class CleanupResponse(BaseModel):
    job_id: str
    message: str
    files_deleted: List[str]
    
class StatsResponse(BaseModel):
    total_jobs: int
    completed: int
    processing: int
    failed: int
    pending: int
    async_jobs: int
    sync_jobs: int
    most_detected_languages: Dict[str, int]