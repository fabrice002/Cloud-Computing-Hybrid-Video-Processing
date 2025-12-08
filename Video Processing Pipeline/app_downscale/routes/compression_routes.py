from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from typing import Optional
import uuid
from datetime import datetime

from models.request_models import VideoCompressionRequest, LocalVideoRequest
from models.response_models import CompressionStatus
from models.enums import VideoSourceType, JobStatus
from services.job_manager import JobManager
from services.video_downscaler import VideoDownscaler
from utils.file_utils import validate_file_extension
from config.settings import Settings

router = APIRouter(prefix="/api/compress", tags=["compression"])

# Shared instances
job_manager = JobManager()
downscaler = VideoDownscaler()

# Helper function for synchronous processing
async def process_job_sync(
    job_id: str,
    source_type: VideoSourceType,
    process_func,
    *args
) -> dict:
    """Process a job synchronously with proper error handling"""
    try:
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            f"Processing {source_type.value} video synchronously..."
        )
        
        result = await process_func(*args)
        
        job_manager.update_job(
            job_id,
            JobStatus.COMPLETED,
            f"{source_type.value} video compression completed successfully",
            output_path=result["output_file"],  # Store output path
            metadata=result,
            completed_at=datetime.now().isoformat()
        )
        
        return result
        
    except Exception as e:
        job_manager.update_job(
            job_id,
            JobStatus.FAILED,
            f"Error: {str(e)}",
            error=str(e),
            failed_at=datetime.now().isoformat()
        )
        raise

# Background task functions
async def process_video_from_url(
    job_id: str,
    video_url: str,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Process video compression from URL and return result"""
    try:
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Downloading video..."
        )
        
        input_path = await downscaler.download_video(video_url, job_id)
        
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Compressing video...",
            input_path=str(input_path)
        )
        
        result = downscaler.compress_video(
            input_path, resolution, crf_value, job_id, custom_filename
        )
        
        # Update job with output path
        job_manager.update_job(
            job_id,
            JobStatus.COMPLETED,
            "Video compression completed successfully",
            output_path=result["output_file"],
            metadata=result,
            completed_at=datetime.now().isoformat()
        )
        
        return result
        
    except Exception as e:
        job_manager.update_job(
            job_id,
            JobStatus.FAILED,
            f"Error: {str(e)}",
            error=str(e),
            failed_at=datetime.now().isoformat()
        )
        raise

async def process_video_from_url_sync(
    job_id: str,
    video_url: str,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Synchronous wrapper for URL processing"""
    return await process_video_from_url(job_id, video_url, resolution, crf_value, custom_filename)

async def process_local_video(
    job_id: str,
    local_path: str,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Process local video compression and return result"""
    try:
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Copying local video..."
        )
        
        input_path = downscaler.copy_local_video(local_path, job_id)
        
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Compressing video...",
            input_path=str(input_path)
        )
        
        result = downscaler.compress_video(
            input_path, resolution, crf_value, job_id, custom_filename
        )
        
        # Update job with output path
        job_manager.update_job(
            job_id,
            JobStatus.COMPLETED,
            "Local video compression completed successfully",
            output_path=result["output_file"],
            metadata=result,
            completed_at=datetime.now().isoformat()
        )
        
        return result
        
    except Exception as e:
        job_manager.update_job(
            job_id,
            JobStatus.FAILED,
            f"Error: {str(e)}",
            error=str(e),
            failed_at=datetime.now().isoformat()
        )
        raise

async def process_local_video_sync(
    job_id: str,
    local_path: str,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Synchronous wrapper for local video processing"""
    return await process_local_video(job_id, local_path, resolution, crf_value, custom_filename)

async def process_uploaded_video(
    job_id: str,
    file: UploadFile,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Process uploaded video compression and return result"""
    try:
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Saving uploaded video..."
        )
        
        input_path = await downscaler.save_uploaded_video(file, job_id)
        
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Compressing video...",
            input_path=str(input_path)
        )
        
        result = downscaler.compress_video(
            input_path, resolution, crf_value, job_id, custom_filename
        )
        
        # Update job with output path
        job_manager.update_job(
            job_id,
            JobStatus.COMPLETED,
            "Uploaded video compression completed successfully",
            output_path=result["output_file"],
            metadata=result,
            completed_at=datetime.now().isoformat()
        )
        
        return result
        
    except Exception as e:
        job_manager.update_job(
            job_id,
            JobStatus.FAILED,
            f"Error: {str(e)}",
            error=str(e),
            failed_at=datetime.now().isoformat()
        )
        raise

async def process_uploaded_video_sync(
    job_id: str,
    file: UploadFile,
    resolution: str,
    crf_value: int,
    custom_filename: Optional[str]
) -> dict:
    """Synchronous wrapper for uploaded video processing"""
    return await process_uploaded_video(job_id, file, resolution, crf_value, custom_filename)

@router.post("/url", response_model=CompressionStatus)
async def compress_video_url(
    request: VideoCompressionRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = True
):
    """
    Download and compress video from URL
    
    Parameters:
    - async_mode: If True, process in background; if False, wait for completion
    """
    job_id = job_manager.create_job(
        source_type=VideoSourceType.URL,
        video_url=str(request.video_url),
        resolution=request.resolution.value,
        crf_value=request.crf_value,
        async_mode=async_mode
    )
    
    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_video_from_url,
            job_id,
            str(request.video_url),
            request.resolution.value,
            request.crf_value,
            request.custom_filename
        )
        
        return CompressionStatus(
            job_id=job_id,
            source_type=VideoSourceType.URL,
            status=JobStatus.PENDING,
            message="Video compression job started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            result = await process_job_sync(
                job_id,
                VideoSourceType.URL,
                process_video_from_url_sync,
                job_id,
                str(request.video_url),
                request.resolution.value,
                request.crf_value,
                request.custom_filename
            )
            
            return CompressionStatus(
                job_id=job_id,
                source_type=VideoSourceType.URL,
                status=JobStatus.COMPLETED,
                message="Video compression completed successfully",
                output_path=result["output_file"],
                metadata=result,
                async_mode=async_mode
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Video compression failed: {str(e)}"
            )

@router.post("/local", response_model=CompressionStatus)
async def compress_video_local(
    request: LocalVideoRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = True
):
    """
    Compress local video file
    
    Parameters:
    - async_mode: If True, process in background; if False, wait for completion
    """
    job_id = job_manager.create_job(
        source_type=VideoSourceType.LOCAL,
        local_path=request.local_path,
        resolution=request.resolution.value,
        crf_value=request.crf_value,
        async_mode=async_mode
    )
    
    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_local_video,
            job_id,
            request.local_path,
            request.resolution.value,
            request.crf_value,
            request.custom_filename
        )
        
        return CompressionStatus(
            job_id=job_id,
            source_type=VideoSourceType.LOCAL,
            status=JobStatus.PENDING,
            message="Local video compression job started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            result = await process_job_sync(
                job_id,
                VideoSourceType.LOCAL,
                process_local_video_sync,
                job_id,
                request.local_path,
                request.resolution.value,
                request.crf_value,
                request.custom_filename
            )
            
            return CompressionStatus(
                job_id=job_id,
                source_type=VideoSourceType.LOCAL,
                status=JobStatus.COMPLETED,
                message="Local video compression completed successfully",
                output_path=result["output_file"],
                metadata=result,
                async_mode=async_mode
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Video compression failed: {str(e)}"
            )

@router.post("/upload", response_model=CompressionStatus)
async def compress_video_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to upload and compress"),
    resolution: str = Form("360p"),
    crf_value: int = Form(28),
    custom_filename: Optional[str] = Form(None),
    async_mode: bool = Form(False, description="If True, process in background; if False, wait for completion")
):
    """
    Upload and compress video file
    
    Parameters:
    - async_mode: If True, process in background; if False, wait for completion
    """
    # Validate file type
    if not validate_file_extension(file.filename, Settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(Settings.ALLOWED_EXTENSIONS)}"
        )
    
    job_id = job_manager.create_job(
        source_type=VideoSourceType.UPLOAD,
        original_filename=file.filename,
        resolution=resolution,
        crf_value=crf_value,
        async_mode=async_mode
    )
    
    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_uploaded_video,
            job_id,
            file,
            resolution,
            crf_value,
            custom_filename
        )
        
        return CompressionStatus(
            job_id=job_id,
            source_type=VideoSourceType.UPLOAD,
            status=JobStatus.PENDING,
            message="Video upload and compression job started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            result = await process_job_sync(
                job_id,
                VideoSourceType.UPLOAD,
                process_uploaded_video_sync,
                job_id,
                file,
                resolution,
                crf_value,
                custom_filename
            )
            
            return CompressionStatus(
                job_id=job_id,
                source_type=VideoSourceType.UPLOAD,
                status=JobStatus.COMPLETED,
                message="Video compression completed successfully",
                output_path=result["output_file"],
                metadata=result,
                async_mode=async_mode
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Video compression failed: {str(e)}"
            )