# models/request_models.py
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional
from models.enums import ResolutionEnum

class VideoCompressionRequest(BaseModel):
    """Request model for video compression from URL"""
    video_url: HttpUrl = Field(..., description="URL of the video to download")
    resolution: ResolutionEnum = Field(default=ResolutionEnum.R360P, description="Target resolution")
    crf_value: int = Field(default=28, ge=18, le=30, description="CRF quality parameter")
    custom_filename: Optional[str] = Field(None, description="Custom output filename")
    
    @field_validator('crf_value')
    def validate_crf(cls, v):
        if not 18 <= v <= 30:
            raise ValueError('CRF value must be between 18 and 30')
        return v

class LocalVideoRequest(BaseModel):
    """Request model for local video compression"""
    local_path: str = Field(..., description="Local file path to compress")
    resolution: ResolutionEnum = Field(default=ResolutionEnum.R360P, description="Target resolution")
    crf_value: int = Field(default=28, ge=18, le=30, description="CRF quality parameter")
    custom_filename: Optional[str] = Field(None, description="Custom output filename")
    
    @field_validator('local_path')
    def validate_local_path(cls, v):
        import os
        if not os.path.exists(v):
            raise ValueError(f'Local file not found: {v}')
        if not os.path.isfile(v):
            raise ValueError(f'Path is not a file: {v}')
        return v
    
    @field_validator('crf_value')
    def validate_crf(cls, v):
        if not 18 <= v <= 30:
            raise ValueError('CRF value must be between 18 and 30')
        return v

class UploadVideoRequest(BaseModel):
    """Request model for upload video compression"""
    resolution: ResolutionEnum = ResolutionEnum.R360P
    crf_value: int = 28
    custom_filename: Optional[str] = None