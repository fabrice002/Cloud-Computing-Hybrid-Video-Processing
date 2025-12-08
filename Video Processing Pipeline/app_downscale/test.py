"""
FastAPI Video Compression Service
==================================
Professional API for compressing videos from URL or local file.

Author: VidP Team
Version: 1.1.0
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field, validator
try:
    # For moviepy 1.x
    from moviepy.editor import VideoFileClip
except ImportError:
    # For moviepy 2.x
    from moviepy import VideoFileClip
from pathlib import Path
from typing import Dict, List, Optional, Literal, Union
from datetime import datetime
import json
import logging
import time
import uuid
import httpx
import os
import shutil
from enum import Enum
import tempfile

# ============================================================================
# CONFIGURATION & LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & MODELS
# ============================================================================

class ResolutionEnum(str, Enum):
    """Supported video resolutions"""
    R1080P = "1080p"
    R720P = "720p"
    R480P = "480p"
    R360P = "360p"
    R240P = "240p"


class VideoSourceType(str, Enum):
    """Video source types"""
    URL = "url"
    LOCAL = "local"
    UPLOAD = "upload"


class VideoCompressionRequest(BaseModel):
    """
    Request model for video compression from URL
    
    Attributes:
        video_url: URL of the video to download and compress
        resolution: Target resolution for compression
        crf_value: CRF quality parameter (18-30, lower = better quality)
    """
    video_url: HttpUrl = Field(..., description="URL of the video to download")
    resolution: ResolutionEnum = Field(default=ResolutionEnum.R360P, description="Target resolution")
    crf_value: int = Field(default=28, ge=18, le=30, description="CRF quality parameter")
    custom_filename: Optional[str] = Field(None, description="Custom output filename")
    
    @validator('crf_value')
    def validate_crf(cls, v):
        if not 18 <= v <= 30:
            raise ValueError('CRF value must be between 18 and 30')
        return v


class LocalVideoRequest(BaseModel):
    """
    Request model for local video compression
    
    Attributes:
        local_path: Local file path to compress
        resolution: Target resolution for compression
        crf_value: CRF quality parameter (18-30, lower = better quality)
    """
    local_path: str = Field(..., description="Local file path to compress")
    resolution: ResolutionEnum = Field(default=ResolutionEnum.R360P, description="Target resolution")
    crf_value: int = Field(default=28, ge=18, le=30, description="CRF quality parameter")
    custom_filename: Optional[str] = Field(None, description="Custom output filename")
    
    @validator('local_path')
    def validate_local_path(cls, v):
        if not os.path.exists(v):
            raise ValueError(f'Local file not found: {v}')
        if not os.path.isfile(v):
            raise ValueError(f'Path is not a file: {v}')
        return v
    
    @validator('crf_value')
    def validate_crf(cls, v):
        if not 18 <= v <= 30:
            raise ValueError('CRF value must be between 18 and 30')
        return v


class CompressionStatus(BaseModel):
    """
    Response model for compression status
    
    Attributes:
        job_id: Unique identifier for the compression job
        source_type: Type of video source (url/local/upload)
        status: Current status of the job
        message: Human-readable status message
        output_path: Path to compressed video (when completed)
        metadata: Additional processing information
    """
    job_id: str
    source_type: VideoSourceType
    status: Literal["pending", "processing", "completed", "failed"]
    message: str
    output_path: Optional[str] = None
    metadata: Optional[Dict] = None


# ============================================================================
# VIDEO DOWNSCALER CLASS
# ============================================================================

class VideoDownscaler:
    """
    Professional video compression service with multiple input sources
    """
    
    def __init__(self, base_dir: str = "video_storage"):
        """
        Initialize the video downscaler
        
        Args:
            base_dir: Base directory for storing videos
        """
        self.resolutions = {
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240
        }
        self.base_dir = Path(base_dir)
        self.downloads_dir = self.base_dir / "downloads"
        self.compressed_dir = self.base_dir / "compressed"
        self.uploads_dir = self.base_dir / "uploads"
        
        # Create directories
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.compressed_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Job storage
        self.jobs: Dict[str, Dict] = {}
    
    async def download_video(self, video_url: str, job_id: str) -> Path:
        """
        Download video from URL
        
        Args:
            video_url: URL of the video to download
            job_id: Unique job identifier
            
        Returns:
            Path: Path to the downloaded video file
            
        Raises:
            HTTPException: If download fails
        """
        try:
            logger.info(f"Downloading video from {video_url}")
            
            # Generate unique filename
            filename = f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            download_path = self.downloads_dir / filename
            
            # Download with streaming
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream('GET', video_url) as response:
                    response.raise_for_status()
                    
                    with open(download_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
            
            logger.info(f"Video downloaded: {download_path}")
            return download_path
            
        except httpx.HTTPError as e:
            logger.error(f"Download failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")
    
    def copy_local_video(self, local_path: str, job_id: str) -> Path:
        """
        Copy local video to working directory
        
        Args:
            local_path: Path to local video file
            job_id: Unique job identifier
            
        Returns:
            Path: Path to the copied video file
            
        Raises:
            HTTPException: If copy fails
        """
        try:
            logger.info(f"Copying local video from {local_path}")
            
            # Generate unique filename
            original_filename = Path(local_path).name
            filename = f"{job_id}_{original_filename}"
            copy_path = self.downloads_dir / filename
            
            # Copy file
            shutil.copy2(local_path, copy_path)
            
            logger.info(f"Local video copied: {copy_path}")
            return copy_path
            
        except Exception as e:
            logger.error(f"Failed to copy local video: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to copy local video: {str(e)}")
    
    async def save_uploaded_video(self, file: UploadFile, job_id: str) -> Path:
        """
        Save uploaded video file
        
        Args:
            file: Uploaded file
            job_id: Unique job identifier
            
        Returns:
            Path: Path to the saved video file
            
        Raises:
            HTTPException: If save fails
        """
        try:
            logger.info(f"Saving uploaded video: {file.filename}")
            
            # Generate safe filename
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            filename = f"{job_id}_{safe_filename}"
            save_path = self.uploads_dir / filename
            
            # Save uploaded file
            with open(save_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            logger.info(f"Uploaded video saved: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"Failed to save uploaded video: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded video: {str(e)}")
    
    def get_video_metadata(self, clip: VideoFileClip) -> Dict:
        """
        Extract video metadata
        
        Args:
            clip: VideoFileClip object
            
        Returns:
            Dict: Video metadata including duration, fps, size, etc.
        """
        return {
            "duration": round(clip.duration, 2),
            "fps": clip.fps,
            "size": clip.size,
            "original_resolution": f"{clip.size[1]}p",
            "has_audio": clip.audio is not None
        }
    
    def calculate_compression_ratio(self, original_path: Path, compressed_path: Path) -> float:
        """
        Calculate compression ratio
        
        Args:
            original_path: Path to original video
            compressed_path: Path to compressed video
            
        Returns:
            float: Compression ratio (compressed_size / original_size)
        """
        original_size = original_path.stat().st_size
        compressed_size = compressed_path.stat().st_size
        return compressed_size / original_size if original_size > 0 else 0
    
    def compress_video(self, input_path: Path, resolution: str, crf_value: int, job_id: str, custom_filename: Optional[str] = None) -> Dict:
        """
        Compress video to specified resolution
        
        Args:
            input_path: Path to input video file
            resolution: Target resolution (e.g., '360p', '720p')
            crf_value: CRF quality parameter (18-30)
            job_id: Unique job identifier
            custom_filename: Optional custom output filename
            
        Returns:
            Dict: Processing information including output path, metadata, and stats
            
        Raises:
            ValueError: If resolution is not supported
            FileNotFoundError: If input file doesn't exist
        """
        start_time = time.time()
        
        if resolution not in self.resolutions:
            raise ValueError(f"Unsupported resolution: {resolution}")
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        
        # Create resolution-specific output directory
        output_dir = self.compressed_dir / resolution
        output_dir.mkdir(parents=True, exist_ok=True)
        
        processing_info = {
            "job_id": job_id,
            "input_file": str(input_path),
            "resolution_target": resolution,
            "crf_value": crf_value,
            "status": "processing",
            "timestamp": datetime.now().isoformat()
        }
        
        clip = None
        resized_clip = None
        
        try:
            # Load video
            clip = VideoFileClip(str(input_path))
            
            # Get original metadata
            original_metadata = self.get_video_metadata(clip)
            processing_info["original_metadata"] = original_metadata
            
            # Resize video
            new_height = self.resolutions[resolution]
            resized_clip = clip.resized(height=new_height)
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if custom_filename:
                # Ensure safe filename and add extension
                safe_name = Path(custom_filename).stem
                safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
                output_filename = f"{job_id}_{safe_name}_{timestamp}.mp4"
            else:
                original_name = input_path.stem
                output_filename = f"{job_id}_{original_name}_{resolution}_{timestamp}.mp4"
            
            output_path = output_dir / output_filename
            
            # Encoding parameters
            write_kwargs = {
                "codec": "libx264",
                "preset": "medium",
                "threads": 4,
                "ffmpeg_params": ["-crf", str(crf_value), "-movflags", "+faststart"]
            }
            
            logger.info(f"Compressing {input_path.name} -> {resolution} (CRF={crf_value})")
            
            # Encode with or without audio
            if clip.audio is not None:
                write_kwargs.update({"audio_codec": "aac", "audio_bitrate": "96k"})
                resized_clip.write_videofile(str(output_path), **write_kwargs)
            else:
                resized_clip.write_videofile(str(output_path), audio=False, **write_kwargs)
            
            # Calculate final metrics
            processing_time = time.time() - start_time
            compression_ratio = self.calculate_compression_ratio(input_path, output_path)
            
            processing_info.update({
                "output_file": str(output_path),
                "output_path_relative": str(output_path.relative_to(self.base_dir)),
                "processing_time_seconds": round(processing_time, 2),
                "compression_ratio": round(compression_ratio, 3),
                "original_size_mb": round(input_path.stat().st_size / (1024 * 1024), 2),
                "final_size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
                "status": "completed"
            })
            
            # Save metadata
            metadata_file = output_dir / f"{job_id}_metadata_{timestamp}.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(processing_info, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Compression completed: {output_path}")
            logger.info(f"Compression ratio: {compression_ratio:.1%} | Time: {processing_time:.1f}s")
            
            return processing_info
            
        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            logger.error(error_msg)
            processing_info.update({
                "status": "failed",
                "error": str(e)
            })
            raise
        finally:
            # Clean up resources
            if clip is not None:
                clip.close()
            if resized_clip is not None:
                resized_clip.close()


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Video Compression API",
    description="Professional video compression service supporting URLs, local files, and uploads",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

downscaler = VideoDownscaler()


@app.get("/")
async def root():
    """
    API health check endpoint
    
    Returns:
        Dict: API status and information
    """
    return {
        "service": "Video Compression API v1.1",
        "status": "running",
        "version": "1.1.0",
        "features": [
            "Compress videos from URLs",
            "Compress local video files",
            "Upload and compress videos",
            "Multiple resolutions (240p to 1080p)",
            "Adjustable quality (CRF 18-30)"
        ],
        "endpoints": {
            "compress_url": "/api/compress/url",
            "compress_local": "/api/compress/local",
            "compress_upload": "/api/compress/upload",
            "status": "/api/status/{job_id}",
            "download": "/api/download/{job_id}",
            "cleanup": "/api/cleanup/{job_id}"
        }
    }


@app.post("/api/compress/url", response_model=CompressionStatus)
async def compress_video_url(request: VideoCompressionRequest, background_tasks: BackgroundTasks):
    """
    Download and compress video from URL
    
    Args:
        request: VideoCompressionRequest containing video_url, resolution, and crf_value
        background_tasks: FastAPI background tasks
        
    Returns:
        CompressionStatus: Job information with job_id for tracking
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    downscaler.jobs[job_id] = {
        "source_type": VideoSourceType.URL,
        "status": "pending",
        "message": "Job queued for processing",
        "created_at": datetime.now().isoformat(),
        "video_url": str(request.video_url),
        "resolution": request.resolution.value,
        "crf_value": request.crf_value
    }
    
    # Add processing to background tasks
    background_tasks.add_task(
        process_video_from_url,
        job_id,
        str(request.video_url),
        request.resolution.value,
        request.crf_value,
        request.custom_filename
    )
    
    logger.info(f"New URL compression job created: {job_id}")
    
    return CompressionStatus(
        job_id=job_id,
        source_type=VideoSourceType.URL,
        status="pending",
        message="Video compression job started. Use job_id to check status."
    )


@app.post("/api/compress/local", response_model=CompressionStatus)
async def compress_video_local(request: LocalVideoRequest, background_tasks: BackgroundTasks):
    """
    Compress local video file
    
    Args:
        request: LocalVideoRequest containing local_path, resolution, and crf_value
        background_tasks: FastAPI background tasks
        
    Returns:
        CompressionStatus: Job information with job_id for tracking
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    downscaler.jobs[job_id] = {
        "source_type": VideoSourceType.LOCAL,
        "status": "pending",
        "message": "Job queued for processing",
        "created_at": datetime.now().isoformat(),
        "local_path": request.local_path,
        "resolution": request.resolution.value,
        "crf_value": request.crf_value
    }
    
    # Add processing to background tasks
    background_tasks.add_task(
        process_local_video,
        job_id,
        request.local_path,
        request.resolution.value,
        request.crf_value,
        request.custom_filename
    )
    
    logger.info(f"New local file compression job created: {job_id}")
    
    return CompressionStatus(
        job_id=job_id,
        source_type=VideoSourceType.LOCAL,
        status="pending",
        message="Local video compression job started. Use job_id to check status."
    )


@app.post("/api/compress/upload", response_model=CompressionStatus)
async def compress_video_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to upload and compress"),
    resolution: ResolutionEnum = Form(ResolutionEnum.R360P, description="Target resolution"),
    crf_value: int = Form(28, ge=18, le=30, description="CRF quality parameter (18-30)"),
    custom_filename: Optional[str] = Form(None, description="Custom output filename")
):
    """
    Upload and compress video file
    
    Args:
        file: Video file to upload
        resolution: Target resolution
        crf_value: CRF quality parameter
        custom_filename: Custom output filename
        background_tasks: FastAPI background tasks
        
    Returns:
        CompressionStatus: Job information with job_id for tracking
    """
    # Validate file type
    allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    downscaler.jobs[job_id] = {
        "source_type": VideoSourceType.UPLOAD,
        "status": "pending",
        "message": "Job queued for processing",
        "created_at": datetime.now().isoformat(),
        "original_filename": file.filename,
        "resolution": resolution.value,
        "crf_value": crf_value
    }
    
    # Add processing to background tasks
    background_tasks.add_task(
        process_uploaded_video,
        job_id,
        file,
        resolution.value,
        crf_value,
        custom_filename
    )
    
    logger.info(f"New upload compression job created: {job_id}")
    
    return CompressionStatus(
        job_id=job_id,
        source_type=VideoSourceType.UPLOAD,
        status="pending",
        message="Video upload and compression job started. Use job_id to check status."
    )


@app.get("/api/status/{job_id}", response_model=CompressionStatus)
async def get_job_status(job_id: str):
    """
    Get compression job status
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        CompressionStatus: Current job status and information
        
    Raises:
        HTTPException: If job_id not found
    """
    if job_id not in downscaler.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = downscaler.jobs[job_id]
    
    return CompressionStatus(
        job_id=job_id,
        source_type=job_data["source_type"],
        status=job_data["status"],
        message=job_data.get("message", ""),
        output_path=job_data.get("output_path"),
        metadata=job_data.get("metadata")
    )


@app.get("/api/download/{job_id}")
async def download_compressed_video(job_id: str):
    """
    Download compressed video file
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        FileResponse: Compressed video file
        
    Raises:
        HTTPException: If job not found or not completed
    """
    if job_id not in downscaler.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = downscaler.jobs[job_id]
    
    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job_data['status']}"
        )
    
    output_path = Path(job_data["output_path"])
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Compressed video file not found")
    
    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=output_path.name
    )


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    """
    Delete job files and remove from tracking
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Dict: Cleanup confirmation
        
    Raises:
        HTTPException: If job not found
    """
    if job_id not in downscaler.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = downscaler.jobs[job_id]
    
    # Delete files if they exist
    files_deleted = []
    
    if "input_path" in job_data:
        input_path = Path(job_data["input_path"])
        if input_path.exists():
            input_path.unlink()
            files_deleted.append(str(input_path))
    
    if "output_path" in job_data:
        output_path = Path(job_data["output_path"])
        if output_path.exists():
            output_path.unlink()
            files_deleted.append(str(output_path))
    
    # Remove from jobs
    del downscaler.jobs[job_id]
    
    logger.info(f"🗑️ Cleaned up job: {job_id}")
    
    return {
        "job_id": job_id,
        "message": "Job cleaned up successfully",
        "files_deleted": files_deleted
    }


# ============================================================================
# BACKGROUND TASK HANDLERS
# ============================================================================

async def process_video_from_url(job_id: str, video_url: str, resolution: str, crf_value: int, custom_filename: Optional[str]):
    """
    Background task to process video compression from URL
    
    Args:
        job_id: Unique job identifier
        video_url: URL of video to download
        resolution: Target resolution
        crf_value: CRF quality parameter
        custom_filename: Custom output filename
    """
    try:
        # Update status to processing
        downscaler.jobs[job_id].update({
            "status": "processing",
            "message": "Downloading video..."
        })
        
        # Download video
        input_path = await downscaler.download_video(video_url, job_id)
        
        downscaler.jobs[job_id].update({
            "message": "Compressing video...",
            "input_path": str(input_path)
        })
        
        # Compress video
        result = downscaler.compress_video(input_path, resolution, crf_value, job_id, custom_filename)
        
        # Update job with results
        downscaler.jobs[job_id].update({
            "status": "completed",
            "message": "Video compression completed successfully",
            "output_path": result["output_file"],
            "metadata": result,
            "completed_at": datetime.now().isoformat()
        })
        
        logger.info(f"Job completed successfully: {job_id}")
        
    except Exception as e:
        logger.error(f"Job failed: {job_id} - {str(e)}")
        downscaler.jobs[job_id].update({
            "status": "failed",
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })


async def process_local_video(job_id: str, local_path: str, resolution: str, crf_value: int, custom_filename: Optional[str]):
    """
    Background task to process local video compression
    
    Args:
        job_id: Unique job identifier
        local_path: Local file path
        resolution: Target resolution
        crf_value: CRF quality parameter
        custom_filename: Custom output filename
    """
    try:
        # Update status to processing
        downscaler.jobs[job_id].update({
            "status": "processing",
            "message": "Copying local video..."
        })
        
        # Copy local video
        input_path = downscaler.copy_local_video(local_path, job_id)
        
        downscaler.jobs[job_id].update({
            "message": "Compressing video...",
            "input_path": str(input_path)
        })
        
        # Compress video
        result = downscaler.compress_video(input_path, resolution, crf_value, job_id, custom_filename)
        
        # Update job with results
        downscaler.jobs[job_id].update({
            "status": "completed",
            "message": "Local video compression completed successfully",
            "output_path": result["output_file"],
            "metadata": result,
            "completed_at": datetime.now().isoformat()
        })
        
        logger.info(f"Local job completed successfully: {job_id}")
        
    except Exception as e:
        logger.error(f"Local job failed: {job_id} - {str(e)}")
        downscaler.jobs[job_id].update({
            "status": "failed",
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })


async def process_uploaded_video(job_id: str, file: UploadFile, resolution: str, crf_value: int, custom_filename: Optional[str]):
    """
    Background task to process uploaded video compression
    
    Args:
        job_id: Unique job identifier
        file: Uploaded file
        resolution: Target resolution
        crf_value: CRF quality parameter
        custom_filename: Custom output filename
    """
    try:
        # Update status to processing
        downscaler.jobs[job_id].update({
            "status": "processing",
            "message": "Saving uploaded video..."
        })
        
        # Save uploaded file
        input_path = await downscaler.save_uploaded_video(file, job_id)
        
        downscaler.jobs[job_id].update({
            "message": "Compressing video...",
            "input_path": str(input_path)
        })
        
        # Compress video
        result = downscaler.compress_video(input_path, resolution, crf_value, job_id, custom_filename)
        
        # Update job with results
        downscaler.jobs[job_id].update({
            "status": "completed",
            "message": "Uploaded video compression completed successfully",
            "output_path": result["output_file"],
            "metadata": result,
            "completed_at": datetime.now().isoformat()
        })
        
        logger.info(f"Upload job completed successfully: {job_id}")
        
    except Exception as e:
        logger.error(f"Upload job failed: {job_id} - {str(e)}")
        downscaler.jobs[job_id].update({
            "status": "failed",
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize API on startup"""
    logger.info("Video Compression API v1.1 started")
    logger.info(f"Storage directory: {downscaler.base_dir.absolute()}")
    logger.info("Available endpoints:")
    logger.info("- POST /api/compress/url - Compress from URL")
    logger.info("- POST /api/compress/local - Compress local file")
    logger.info("- POST /api/compress/upload - Upload and compress")
    logger.info("- GET /api/status/{job_id} - Check job status")
    logger.info("- GET /api/download/{job_id} - Download result")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on API shutdown"""
    logger.info("Video Compression API shutting down")


# ============================================================================
# TEST ENDPOINTS
# ============================================================================

@app.post("/api/test/local")
async def test_local_file():
    """
    Test endpoint for local file compression
    
    Example: Test with "D:/Music/Bramsito_-_Sale_mood_ft._Booba(0).mp4"
    """
    test_path = "D:/Music/Bramsito_-_Sale_mood_ft._Booba(0).mp4"
    
    if not os.path.exists(test_path):
        return {
            "status": "error",
            "message": f"Test file not found: {test_path}",
            "suggestion": "Update the test_path variable with a valid local file path"
        }
    
    # Generate job ID for test
    job_id = str(uuid.uuid4())
    
    # Store test job
    downscaler.jobs[job_id] = {
        "source_type": VideoSourceType.LOCAL,
        "status": "processing",
        "message": "Test compression in progress",
        "created_at": datetime.now().isoformat(),
        "local_path": test_path
    }
    
    # Run test compression
    try:
        # Copy local file
        input_path = downscaler.copy_local_video(test_path, job_id)
        
        # Compress to 360p
        result = downscaler.compress_video(
            input_path, 
            resolution="360p", 
            crf_value=28, 
            job_id=job_id,
            custom_filename="test_compression"
        )
        
        downscaler.jobs[job_id].update({
            "status": "completed",
            "output_path": result["output_file"],
            "metadata": result
        })
        
        return {
            "status": "success",
            "job_id": job_id,
            "message": "Test compression completed successfully",
            "result": {
                "original_size_mb": result["original_size_mb"],
                "compressed_size_mb": result["final_size_mb"],
                "compression_ratio": result["compression_ratio"],
                "processing_time": result["processing_time_seconds"],
                "download_url": f"/api/download/{job_id}"
            }
        }
        
    except Exception as e:
        downscaler.jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })
        
        return {
            "status": "error",
            "job_id": job_id,
            "message": f"Test compression failed: {str(e)}"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)