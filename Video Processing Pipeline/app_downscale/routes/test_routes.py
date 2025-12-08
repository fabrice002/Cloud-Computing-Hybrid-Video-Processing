from fastapi import APIRouter, HTTPException
import os
from pathlib import Path
import uuid

from models.response_models import TestResult
from models.enums import VideoSourceType, JobStatus
from services.job_manager import JobManager
from services.video_downscaler import VideoDownscaler

router = APIRouter(prefix="/api/test", tags=["test"])
job_manager = JobManager()
downscaler = VideoDownscaler()

@router.post("/local", response_model=TestResult)
async def test_local_file():
    """Test endpoint for local file compression"""
    test_path = "D:/Music/Bramsito_-_Sale_mood_ft._Booba(0).mp4"
    
    if not os.path.exists(test_path):
        return TestResult(
            status="error",
            job_id="",
            message=f"Test file not found: {test_path}",
            result=None
        )
    
    job_id = job_manager.create_job(
        source_type=VideoSourceType.LOCAL,
        local_path=test_path
    )
    
    try:
        job_manager.update_job(
            job_id,
            JobStatus.PROCESSING,
            "Test compression in progress"
        )
        
        input_path = downscaler.copy_local_video(test_path, job_id)
        
        result = downscaler.compress_video(
            input_path, 
            resolution="360p", 
            crf_value=28, 
            job_id=job_id,
            custom_filename="test_compression"
        )
        
        job_manager.update_job(
            job_id,
            JobStatus.COMPLETED,
            "Test compression completed successfully",
            output_path=result["output_file"],
            metadata=result
        )
        
        return TestResult(
            status="success",
            job_id=job_id,
            message="Test compression completed successfully",
            result={
                "original_size_mb": result["original_size_mb"],
                "compressed_size_mb": result["final_size_mb"],
                "compression_ratio": result["compression_ratio"],
                "processing_time": result["processing_time_seconds"],
                "download_url": f"/api/download/{job_id}"
            }
        )
        
    except Exception as e:
        job_manager.update_job(
            job_id,
            JobStatus.FAILED,
            f"Test compression failed: {str(e)}"
        )
        
        return TestResult(
            status="error",
            job_id=job_id,
            message=f"Test compression failed: {str(e)}",
            result=None
        )