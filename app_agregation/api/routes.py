"""
API route definitions for video processing endpoints.

This module defines the REST API endpoints for the video aggregation service,
handling video uploads, processing workflows, and file downloads.
"""

from typing import Optional
import os
import shutil
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
import httpx

from config.settings import settings
from services.external_services import ExternalServices
from services.ffmpeg_service import FFmpegService
from utils.file_utils import cleanup_files, validate_file_size
from utils.exceptions import handle_service_error

logger = logging.getLogger(__name__)

# Initialize router with prefix and tags
router = APIRouter(prefix="/api", tags=["Video Processing"])

# Ensure storage directory exists
STORAGE_DIR = settings.BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.post(
    "/process-video-combined/",
    summary="Process video with subtitles and compression",
    response_description="Returns processed video download URL",
    status_code=status.HTTP_200_OK
)
async def process_video_combined(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to process (MP4 format)"),
    model_name: str = Form(default="base", description="Whisper model for subtitle generation"),
    resolution: str = Form(default="360p", description="Target video resolution"),
    crf_value: int = Form(default=28, ge=0, le=51, description="Video quality (0-51, lower is better)")
) -> dict:
    """
    Complete video processing workflow combining subtitle generation, burning, and compression.
    
    This endpoint orchestrates the following steps:
    1. Upload and validate the video file
    2. Generate subtitles using the Whisper model (fetching JSON text)
    3. Burn subtitles into the video locally
    4. Compress the video to target resolution via external service
    5. Store the final video and return download URL
    """
    job_id = f"job_{os.urandom(4).hex()}"
    logger.info(f"[{job_id}] Starting video processing for: {file.filename}")
    
    # Define file paths
    original_video_path = settings.TEMP_DIR / f"{job_id}_original.mp4"
    burned_video_path = settings.TEMP_DIR / f"{job_id}_burned.mp4"
    # SRT path will be determined by ExternalServices but typically matches video path
    
    # Track temporary files for cleanup (exclude final storage file)
    temp_files = [original_video_path, burned_video_path]
    
    try:
        # Step 1: Save and validate uploaded file
        logger.info(f"[{job_id}] Saving uploaded file: {file.filename}")
        with open(original_video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        if not validate_file_size(original_video_path, settings.MAX_UPLOAD_SIZE):
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE / (1024*1024):.0f}MB"
            )
        
        # Step 2: Initialize HTTP client for external service calls
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            
            # Step 3: Generate subtitles (Get JSON text, save as .srt)
            logger.info(f"[{job_id}] Step 1/3: Generating subtitles (model: {model_name})")
            generated_srt_path = await ExternalServices.fetch_subtitles(
                client=client,
                video_path=original_video_path,
                original_filename=file.filename,
                model_name=model_name
            )
            temp_files.append(generated_srt_path)
            
            # Step 4: Burn subtitles into video locally
            logger.info(f"[{job_id}] Step 2/3: Burning subtitles into video")
            FFmpegService.burn_subtitles(
                video_path=original_video_path,
                srt_path=generated_srt_path,
                output_path=burned_video_path
            )
            
            # Step 5: Compress and store final video
            logger.info(f"[{job_id}] Step 3/3: Compressing video (resolution: {resolution}, CRF: {crf_value})")
            
            compressed_filename = await ExternalServices.compress_video(
                client=client,
                video_path=burned_video_path,
                filename=f"{job_id}_final.mp4",
                resolution=resolution,
                crf=crf_value
            )
        
        # Construct download URL
        # download_url = f"/api/download/{compressed_filename}"
        
        download_url = f"{settings.COMPRESSION_DOWNLOAD_BASE_URL}/{compressed_filename}"
        
        # Schedule cleanup of temporary files in background
        background_tasks.add_task(cleanup_files, temp_files)
        
        logger.info(f"[{job_id}] Video processing completed successfully")
        
        return {
            "status": "success",
            "job_id": job_id,
            "message": "Video processed and stored successfully",
            "final_video_url": download_url,
            "metadata": {
                "original_filename": file.filename,
                "model_used": model_name,
                "resolution": resolution,
                "crf": crf_value
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        cleanup_files(temp_files)
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Processing failed: {str(e)}", exc_info=True)
        cleanup_files(temp_files)
        raise handle_service_error(e, f"Job {job_id}")


@router.get(
    "/download/{filename}",
    summary="Download processed video",
    response_class=FileResponse,
    responses={
        200: {"description": "Video file stream"},
        404: {"description": "Video not found or expired"}
    }
)
async def download_video(filename: str) -> FileResponse:
    """
    Serve a processed video file from local storage.
    """
    # Assuming the file is in STORAGE_DIR or Settings.OUTPUT_DIR
    file_path = STORAGE_DIR / filename
    
    # Fallback to shared output dir if configured
    if not file_path.exists() and hasattr(settings, 'SHARED_COMPRESSION_DIR'):
         file_path = settings.SHARED_COMPRESSION_DIR / filename

    if not file_path.exists():
        logger.warning(f"Download attempt for non-existent file: {filename}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found or has expired"
        )
    
    if not file_path.is_file():
        logger.error(f"Invalid file path: {filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )
    
    logger.info(f"Serving video file: {filename}")
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


@router.get(
    "/health",
    summary="Health check endpoint",
    response_description="Service health status"
)
async def health_check() -> dict:
    """
    Check service health and availability.
    """
    return {
        "status": "healthy",
        "service": "Video Aggregation Service",
        "version": settings.API_VERSION,
        "storage_available": STORAGE_DIR.exists()
    }