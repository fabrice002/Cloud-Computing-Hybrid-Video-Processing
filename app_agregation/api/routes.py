# app_aggregation/api/routes.py
"""
API route definitions for video processing endpoints.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional
import uuid

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, status, Request
from fastapi.responses import StreamingResponse
import httpx  # <--- Required for downloading the SRT from the other service

from config.settings import settings
from services.ffmpeg_service import FFmpegService
from services.mongodb_service import MongoDBService
from models.video import VideoStatus, VideoCreateRequest, VideoUpdateRequest
from utils.file_utils import cleanup_files, validate_file_size
from utils.exceptions import handle_service_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Video Processing"])

@router.post(
    "/process-video/",
    summary="Process video with SRT URL",
    response_description="Returns video metadata and streaming URL",
    status_code=status.HTTP_200_OK
)
async def process_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="Video file to process (MP4 format)"),
    srt_url: str = Form(..., description="URL to the SRT file (from Subtitle Service)"),
    resolution: str = Form(default="360p", description="Target video resolution"),
    crf_value: int = Form(default=23, ge=0, le=51, description="Video quality (0-51, lower is better)")
) -> dict:
    """
    Process video with provided SRT subtitles, burn them in, compress, and store.
    
    Steps:
    1. Save uploaded video and SRT content
    2. Burn subtitles into video using FFmpeg
    3. Compress the video (optional, can be skipped)
    4. Store final video permanently
    5. Save metadata to MongoDB
    6. Return streaming URL
    """
    # Generate a unique Job ID
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    logger.info(f"[{job_id}] Starting video processing for: {video.filename}")
    
    # Define file paths
    original_video_path = settings.TEMP_DIR / f"{job_id}_original.mp4"
    srt_path = settings.TEMP_DIR / f"{job_id}.srt"
    burned_video_path = settings.TEMP_DIR / f"{job_id}_burned.mp4"
    
    # Final destination path
    final_filename = f"{job_id}_final.mp4"
    final_video_path = settings.VIDEO_STORAGE_DIR / final_filename
    
    # Track temporary files for cleanup
    temp_files = [original_video_path, srt_path, burned_video_path]
    
    # Resolution mapping
    resolution_map = {
        "1080p": "1920x1080",
        "720p": "1280x720",
        "480p": "854x480",
        "360p": "640x360"
    }
    target_resolution = resolution_map.get(resolution, "640x360")
    
    video_id = None
    
    try:
        # Step 1: Save uploaded video
        logger.info(f"[{job_id}] Saving uploaded video: {video.filename}")
        settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(original_video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        if hasattr(settings, 'MAX_UPLOAD_SIZE') and not validate_file_size(original_video_path, settings.MAX_UPLOAD_SIZE):
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size"
            )
        
        # Step 2: Download SRT content from the provided URL
        logger.info(f"[{job_id}] Downloading SRT from: {srt_url}")
        
        async with httpx.AsyncClient() as client:
            try:
                # Add a timeout to prevent hanging
                response = await client.get(srt_url, timeout=10.0)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Failed to download subtitles. Status: {response.status_code}"
                    )
                
                # Write the downloaded content to the local temp SRT file
                with open(srt_path, "wb") as srt_file:
                    srt_file.write(response.content)
                    
            except httpx.RequestError as e:
                raise HTTPException(status_code=400, detail=f"Error connecting to subtitle service: {str(e)}")

        # Step 3: Create initial MongoDB entry
        streaming_url = f"{settings.API_URL}/api/video_storage/{final_filename}"
        
        video_create = VideoCreateRequest(
            filename=video.filename,
            file_path=str(final_video_path),
            link=streaming_url,
            status=VideoStatus.PROCESSING,
            file_size=original_video_path.stat().st_size
        )
        
        video_metadata = await MongoDBService.create_video(video_create)
        video_id = str(video_metadata.id)
        
        # Step 4: Burn subtitles into video
        logger.info(f"[{job_id}] Burning subtitles into video")
        
        await FFmpegService.burn_subtitles(
            video_path=str(original_video_path),
            srt_path=str(srt_path),
            output_path=str(burned_video_path),
            resolution=target_resolution,
            crf=crf_value
        )
        
        # Step 5: Save final video to storage
        logger.info(f"[{job_id}] Saving final video to storage")
        settings.VIDEO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(burned_video_path, final_video_path)
        
        # Step 6: Get final video information
        video_info = FFmpegService.get_video_metadata(str(final_video_path))
        
        # Step 7: Update MongoDB with success status
        update_data = VideoUpdateRequest(
            status=VideoStatus.SAVED,
            file_size=video_info.get("size"),
            duration=video_info.get("duration"),
            resolution=video_info.get("resolution")
        )
        
        await MongoDBService.update_video(video_id, update_data)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, temp_files)
        
        logger.info(f"[{job_id}] Video processing completed successfully")
        
        return {
            "status": "success",
            "job_id": job_id,
            "video_id": video_id,
            "message": "Video processed and stored successfully",
            "streaming_url": streaming_url,
            "metadata": {
                "original_filename": video.filename,
                "final_filename": final_filename,
                "resolution": video_info.get("resolution"),
                "duration": video_info.get("duration"),
                "file_size": video_info.get("size")
            }
        }
    
    except HTTPException:
        if video_id:
            await MongoDBService.update_video(
                video_id,
                VideoUpdateRequest(status=VideoStatus.FAILED, error_message="HTTP error occurred")
            )
        cleanup_files(temp_files)
        raise
    
    except Exception as e:
        logger.error(f"[{job_id}] Processing failed: {str(e)}", exc_info=True)
        if video_id:
            await MongoDBService.update_video(
                video_id,
                VideoUpdateRequest(status=VideoStatus.FAILED, error_message=str(e))
            )
        cleanup_files(temp_files)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get(
    "/video_storage/{filename}",
    summary="Stream video with range request support",
    response_class=StreamingResponse,
    responses={
        200: {"description": "Video stream"},
        206: {"description": "Partial content (range request)"},
        404: {"description": "Video not found"}
    }
)
async def stream_video(filename: str, request: Request) -> StreamingResponse:
    video_path = settings.VIDEO_STORAGE_DIR / filename
    
    if not video_path.exists():
        logger.warning(f"Stream attempt for non-existent file: {filename}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    
    file_size = video_path.stat().st_size
    range_header = request.headers.get("range")
    
    if range_header:
        range_match = range_header.replace("bytes=", "").split("-")
        try:
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
        except ValueError:
             raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid range format")
        
        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid range")
        
        chunk_size = end - start + 1
        
        def iterfile():
            with open(video_path, "rb") as video_file:
                video_file.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    read_size = min(settings.CHUNK_SIZE, remaining)
                    data = video_file.read(read_size)
                    if not data: break
                    remaining -= len(data)
                    yield data
        
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)
    
    def iterfile():
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(settings.CHUNK_SIZE):
                yield chunk
    
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(iterfile(), headers=headers, media_type="video/mp4")


@router.get("/videos/{video_id}")
async def get_video_metadata(video_id: str) -> dict:
    video = await MongoDBService.get_video(video_id)
    if not video: raise HTTPException(status_code=404, detail="Video not found")
    return video.model_dump(by_alias=True, exclude={"id"})

@router.get("/videos/")
async def list_videos(status: Optional[VideoStatus] = None, limit: int = 100) -> dict:
    videos = await MongoDBService.list_videos(status=status, limit=limit)
    return {"total": len(videos), "videos": [video.model_dump(by_alias=True, exclude={"id"}) for video in videos]}

@router.delete("/videos/{video_id}")
async def delete_video(video_id: str, background_tasks: BackgroundTasks) -> dict:
    video = await MongoDBService.get_video(video_id)
    if not video: raise HTTPException(status_code=404, detail="Video not found")
    video_path = settings.VIDEO_STORAGE_DIR / Path(video.file_path).name
    if video_path.exists(): background_tasks.add_task(cleanup_files, [video_path])
    deleted = await MongoDBService.delete_video(video_id)
    if not deleted: raise HTTPException(status_code=404, detail="Video metadata not found")
    return {"status": "success", "message": f"Video {video_id} deleted successfully"}

@router.get("/health")
async def health_check() -> dict:
    mongo_status = False
    try:
         if MongoDBService._client: mongo_status = True
    except Exception: mongo_status = False
    return {
        "status": "healthy",
        "service": "Video Aggregation Service",
        "version": getattr(settings, "API_VERSION", "1.0.0"),
        "storage_available": settings.VIDEO_STORAGE_DIR.exists(),
        "mongodb_connected": mongo_status
    }