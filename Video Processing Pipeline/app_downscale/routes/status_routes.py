from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path

from models.response_models import CompressionStatus, CleanupResponse, APIInfo
from models.enums import JobStatus
from services.job_manager import JobManager
from utils.file_utils import cleanup_files
from config.settings import Settings

router = APIRouter(prefix="/api", tags=["status"])

# Use the same instance as compression_routes.py
from routes.compression_routes import job_manager

@router.get("/status/{job_id}", response_model=CompressionStatus)
async def get_job_status(job_id: str, request: Request):
    """Get compression job status with video URL"""
    try:
        job_data = job_manager.get_job(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build URLs if job is completed
    video_url = None
    download_url = None
    
    if job_data["status"] == JobStatus.COMPLETED:
        metadata = job_data.get("metadata", {})
        
        # Build video streaming URL
        if "output_path_relative" in metadata:
            # Convert Windows path to URL path
            relative_path = metadata["output_path_relative"].replace("\\", "/")
            video_url = f"{request.base_url}video_storage/{relative_path}"
        
        # Build download URL
        download_url = f"{request.base_url}api/download/{job_id}"
    
    return CompressionStatus(
        job_id=job_id,
        source_type=job_data["source_type"],
        status=job_data["status"],
        message=job_data.get("message", ""),
        output_path=job_data.get("output_path"),
        video_url=video_url,
        download_url=download_url,
        metadata=job_data.get("metadata"),
        async_mode=job_data.get("async_mode", True)
    )

@router.get("/download/{job_id}")
async def download_compressed_video(job_id: str):
    """Download compressed video file"""
    try:
        job_data = job_manager.get_job(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_data["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job_data['status']}"
        )
    
    # Get output path from metadata
    metadata = job_data.get("metadata", {})
    
    if "output_file" not in metadata and "output_path" not in job_data:
        raise HTTPException(status_code=404, detail="Output file path not found")
    
    # Try to get the path from metadata first
    output_path_str = metadata.get("output_file") or job_data.get("output_path")
    
    if not output_path_str:
        raise HTTPException(status_code=404, detail="Output file path not found")
    
    output_path = Path(output_path_str)
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Compressed video file not found")
    
    # Generate filename
    original_filename = job_data.get("original_filename", "compressed_video")
    filename = f"{Path(original_filename).stem}_compressed.mp4"
    
    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Accept-Ranges": "bytes"
        }
    )

@router.delete("/cleanup/{job_id}", response_model=CleanupResponse)
async def cleanup_job(job_id: str):
    """Delete job files and remove from tracking"""
    try:
        job_data = job_manager.get_job(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete files if they exist
    files_to_delete = []
    
    if "input_path" in job_data:
        files_to_delete.append(job_data["input_path"])
    
    if "output_path" in job_data:
        files_to_delete.append(job_data["output_path"])
    
    deleted_files = cleanup_files(files_to_delete)
    
    # Remove from jobs
    job_manager.delete_job(job_id)
    
    return CleanupResponse(
        job_id=job_id,
        message="Job cleaned up successfully",
        files_deleted=deleted_files
    )

@router.get("/stats")
async def get_stats():
    """Get job statistics"""
    return job_manager.get_stats()

@router.get("/info", response_model=APIInfo)
async def get_api_info(request: Request):
    """Get API information"""
    return APIInfo(
        service=Settings.API_TITLE,
        status="running",
        version=Settings.API_VERSION,
        features=[
            "Video compression from URLs",
            "Local file compression",
            "Upload and compress",
            f"Resolutions: {', '.join(Settings.SUPPORTED_RESOLUTIONS.keys())}",
            "Adjustable CRF quality"
        ],
        endpoints={
            "compress_url": f"{request.base_url}api/compress/url",
            "compress_local": f"{request.base_url}api/compress/local",
            "compress_upload": f"{request.base_url}api/compress/upload",
            "status": f"{request.base_url}api/status/{{job_id}}",
            "download": f"{request.base_url}api/download/{{job_id}}"
        }
    )