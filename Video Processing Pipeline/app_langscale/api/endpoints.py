# app_langscale/api/endpoints.py

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from typing import Optional
import uuid
from datetime import datetime
from pathlib import Path

from models.request_models import LanguageDetectionRequest, LocalVideoDetectionRequest
from models.response_models import (
    LanguageDetectionResult, 
    SupportedLanguagesResponse,
    CleanupResponse,
    StatsResponse,
    LanguageInfo
)
from models.enums import DetectionStatus
from services.background_worker import detector, process_detection_job, process_local_detection_job, process_uploaded_detection_job
from utils.constants import SUPPORTED_LANGUAGES
from utils.file_utils import validate_file_extension
from config.settings import Settings

router = APIRouter()

@router.get("/languages", response_model=SupportedLanguagesResponse)
async def get_supported_languages():
    """Get list of supported languages"""
    languages_list = [
        LanguageInfo(code=code, display=display, name=name)
        for code, display, name in SUPPORTED_LANGUAGES
    ]
    
    return SupportedLanguagesResponse(
        total=len(languages_list),
        languages=languages_list
    )

@router.post("/detect", response_model=LanguageDetectionResult)
async def detect_video_language(
    request: LanguageDetectionRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = False
):
    """
    Download video and detect spoken language
    
    Parameters:
    - async_mode: If True, process in background; if False, wait for completion
    """
    job_id = str(uuid.uuid4())
    
    detector.jobs[job_id] = {
        "status": DetectionStatus.PENDING,
        "message": "Job queued for language detection",
        "created_at": datetime.now().isoformat(),
        "video_url": str(request.video_url),
        "duration": request.duration,
        "test_all_languages": request.test_all_languages,
        "async_mode": async_mode
    }
    
    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_detection_job,
            job_id,
            str(request.video_url),
            request.duration,
            request.test_all_languages
        )
        
        return LanguageDetectionResult(
            job_id=job_id,
            status=DetectionStatus.PENDING,
            message="Language detection job started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            # Update status to processing
            detector.jobs[job_id].update({
                "status": DetectionStatus.PROCESSING,
                "message": "Downloading video..."
            })
            
            # Download video
            video_path = await detector.download_video(str(request.video_url), job_id)
            detector.jobs[job_id].update({
                "video_path": str(video_path),
                "message": "Extracting audio..."
            })
            
            # Extract audio
            audio_filename = f"{job_id}_audio.wav"
            audio_path = detector.audio_dir / audio_filename
            
            if not detector.extract_audio(video_path, audio_path):
                raise Exception("Failed to extract audio from video")
            
            detector.jobs[job_id].update({
                "audio_path": str(audio_path),
                "message": "Detecting language..."
            })
            
            # Detect language
            detection_results = detector.detect_language_from_audio(
                audio_path,
                request.duration,
                request.test_all_languages
            )
            
            # Save results
            results_file = detector.save_results(job_id, detection_results)
            
            # Prepare response data
            if detection_results["detected"]:
                message = f"Language detected: {detection_results['language']}"
                transcript_sample = detection_results.get("transcript", "")[:100]
                
                # Get top 3 results for summary
                all_tests = detection_results.get("all_tests", [])
                recognized_tests = [t for t in all_tests if t["recognized"]]
                top_results = sorted(
                    recognized_tests,
                    key=lambda x: x["confidence"],
                    reverse=True
                )[:3]
                
            else:
                message = "No language could be detected from the audio"
                transcript_sample = None
                top_results = []
            
            # Update job with results
            detector.jobs[job_id].update({
                "status": DetectionStatus.COMPLETED,
                "message": message,
                "detected_language": detection_results.get("language"),
                "language_code": detection_results.get("language_code"),
                "language_name": detection_results.get("language_name"),
                "confidence_score": detection_results.get("confidence"),
                "transcript_sample": transcript_sample,
                "all_results": top_results,
                "results_file": str(results_file),
                "metadata": {
                    "total_languages_tested": len(SUPPORTED_LANGUAGES),
                    "languages_recognized": len([t for t in detection_results.get("all_tests", []) if t["recognized"]]),
                    "analysis_duration": request.duration,
                    "video_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2)
                },
                "completed_at": datetime.now().isoformat()
            })
            
            return LanguageDetectionResult(
                job_id=job_id,
                status=DetectionStatus.COMPLETED,
                message=message,
                detected_language=detection_results.get("language"),
                language_code=detection_results.get("language_code"),
                confidence_score=detection_results.get("confidence"),
                transcript_sample=transcript_sample,
                all_results=top_results,
                metadata=detector.jobs[job_id].get("metadata"),
                async_mode=async_mode
            )
            
        except Exception as e:
            detector.jobs[job_id].update({
                "status": DetectionStatus.FAILED,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })
            
            raise HTTPException(
                status_code=500,
                detail=f"Language detection failed: {str(e)}"
            )

@router.post("/detect/local", response_model=LanguageDetectionResult)
async def detect_local_video_language(
    request: LocalVideoDetectionRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = False
):
    """Detect language from local video file"""
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file not found")

    job_id = str(uuid.uuid4())

    detector.jobs[job_id] = {
        "status": DetectionStatus.PENDING,
        "message": "Job queued for local file language detection",
        "created_at": datetime.now().isoformat(),
        "video_path": str(video_path),
        "duration": request.duration,
        "test_all_languages": request.test_all_languages,
        "async_mode": async_mode
    }

    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_local_detection_job,
            job_id,
            str(video_path),
            request.duration,
            request.test_all_languages
        )

        return LanguageDetectionResult(
            job_id=job_id,
            status=DetectionStatus.PENDING,
            message="Local language detection started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            detector.jobs[job_id].update({
                "status": DetectionStatus.PROCESSING,
                "message": "Extracting audio from local file..."
            })

            # Extract audio
            audio_filename = f"{job_id}_audio.wav"
            audio_path = detector.audio_dir / audio_filename

            if not detector.extract_audio(video_path, audio_path):
                raise Exception("Failed to extract audio from video")

            detector.jobs[job_id].update({
                "audio_path": str(audio_path),
                "message": "Detecting language..."
            })

            detection_results = detector.detect_language_from_audio(
                audio_path,
                request.duration,
                request.test_all_languages
            )

            # Save results
            results_file = detector.save_results(job_id, detection_results)

            # Prepare summary
            if detection_results["detected"]:
                message = f"Language detected: {detection_results['language']}"
                transcript_sample = detection_results.get("transcript", "")[:100]

                all_tests = detection_results.get("all_tests", [])
                recognized_tests = [t for t in all_tests if t["recognized"]]
                top_results = sorted(
                    recognized_tests,
                    key=lambda x: x["confidence"],
                    reverse=True
                )[:3]
            else:
                message = "No language could be detected"
                transcript_sample = None
                top_results = []

            detector.jobs[job_id].update({
                "status": DetectionStatus.COMPLETED,
                "message": message,
                "detected_language": detection_results.get("language"),
                "language_code": detection_results.get("language_code"),
                "confidence_score": detection_results.get("confidence"),
                "transcript_sample": transcript_sample,
                "all_results": top_results,
                "results_file": str(results_file),
                "metadata": {
                    "total_languages_tested": len(SUPPORTED_LANGUAGES),
                    "languages_recognized": len([t for t in detection_results.get("all_tests", []) if t["recognized"]]),
                    "analysis_duration": request.duration,
                    "video_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2)
                },
                "completed_at": datetime.now().isoformat()
            })

            return LanguageDetectionResult(
                job_id=job_id,
                status=DetectionStatus.COMPLETED,
                message=message,
                detected_language=detection_results.get("language"),
                language_code=detection_results.get("language_code"),
                confidence_score=detection_results.get("confidence"),
                transcript_sample=transcript_sample,
                all_results=top_results,
                metadata=detector.jobs[job_id].get("metadata"),
                async_mode=async_mode
            )

        except Exception as e:
            detector.jobs[job_id].update({
                "status": DetectionStatus.FAILED,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })

            raise HTTPException(
                status_code=500,
                detail=f"Language detection failed: {str(e)}"
            )

@router.post("/detect/upload", response_model=LanguageDetectionResult)
async def detect_uploaded_video_language(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to upload and detect language"),
    duration: int = Form(30),
    test_all_languages: bool = Form(True),
    async_mode: bool = Form(False, description="If True, process in background; if False, wait for completion")
):
    """
    Upload video and detect spoken language
    
    Parameters:
    - async_mode: If True, process in background; if False, wait for completion
    """
    # Validate file type
    if not validate_file_extension(file.filename, Settings.ALLOWED_VIDEO_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(Settings.ALLOWED_VIDEO_EXTENSIONS)}"
        )
    
    job_id = str(uuid.uuid4())
    
    detector.jobs[job_id] = {
        "status": DetectionStatus.PENDING,
        "message": "Job queued for uploaded file language detection",
        "created_at": datetime.now().isoformat(),
        "original_filename": file.filename,
        "duration": duration,
        "test_all_languages": test_all_languages,
        "async_mode": async_mode
    }
    
    if async_mode:
        # Asynchronous processing
        background_tasks.add_task(
            process_uploaded_detection_job,
            job_id,
            file,
            duration,
            test_all_languages
        )
        
        return LanguageDetectionResult(
            job_id=job_id,
            status=DetectionStatus.PENDING,
            message="Uploaded video language detection started. Use job_id to check status.",
            async_mode=async_mode
        )
    else:
        # Synchronous processing
        try:
            detector.jobs[job_id].update({
                "status": DetectionStatus.PROCESSING,
                "message": "Saving uploaded video..."
            })
            
            # Save uploaded file
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            filename = f"{job_id}_{safe_filename}"
            video_path = detector.videos_dir / filename
            
            with open(video_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            detector.jobs[job_id].update({
                "video_path": str(video_path),
                "message": "Extracting audio..."
            })
            
            # Extract audio
            audio_filename = f"{job_id}_audio.wav"
            audio_path = detector.audio_dir / audio_filename
            
            if not detector.extract_audio(video_path, audio_path):
                raise Exception("Failed to extract audio from video")
            
            detector.jobs[job_id].update({
                "audio_path": str(audio_path),
                "message": "Detecting language..."
            })
            
            # Detect language
            detection_results = detector.detect_language_from_audio(
                audio_path,
                duration,
                test_all_languages
            )
            
            # Save results
            results_file = detector.save_results(job_id, detection_results)
            
            # Prepare response data
            if detection_results["detected"]:
                message = f"Language detected: {detection_results['language']}"
                transcript_sample = detection_results.get("transcript", "")[:100]
                
                # Get top 3 results for summary
                all_tests = detection_results.get("all_tests", [])
                recognized_tests = [t for t in all_tests if t["recognized"]]
                top_results = sorted(
                    recognized_tests,
                    key=lambda x: x["confidence"],
                    reverse=True
                )[:3]
                
            else:
                message = "No language could be detected from the audio"
                transcript_sample = None
                top_results = []
            
            # Update job with results
            detector.jobs[job_id].update({
                "status": DetectionStatus.COMPLETED,
                "message": message,
                "detected_language": detection_results.get("language"),
                "language_code": detection_results.get("language_code"),
                "language_name": detection_results.get("language_name"),
                "confidence_score": detection_results.get("confidence"),
                "transcript_sample": transcript_sample,
                "all_results": top_results,
                "results_file": str(results_file),
                "metadata": {
                    "total_languages_tested": len(SUPPORTED_LANGUAGES),
                    "languages_recognized": len([t for t in detection_results.get("all_tests", []) if t["recognized"]]),
                    "analysis_duration": duration,
                    "video_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2)
                },
                "completed_at": datetime.now().isoformat()
            })
            
            return LanguageDetectionResult(
                job_id=job_id,
                status=DetectionStatus.COMPLETED,
                message=message,
                detected_language=detection_results.get("language"),
                language_code=detection_results.get("language_code"),
                confidence_score=detection_results.get("confidence"),
                transcript_sample=transcript_sample,
                all_results=top_results,
                metadata=detector.jobs[job_id].get("metadata"),
                async_mode=async_mode
            )
            
        except Exception as e:
            detector.jobs[job_id].update({
                "status": DetectionStatus.FAILED,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })
            
            raise HTTPException(
                status_code=500,
                detail=f"Language detection failed: {str(e)}"
            )

@router.get("/status/{job_id}", response_model=LanguageDetectionResult)
async def get_detection_status(job_id: str):
    """Get language detection job status"""
    if job_id not in detector.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = detector.jobs[job_id]
    
    return LanguageDetectionResult(
        job_id=job_id,
        status=job_data["status"],
        message=job_data.get("message", ""),
        detected_language=job_data.get("detected_language"),
        language_code=job_data.get("language_code"),
        language_name=job_data.get("language_name"),
        confidence_score=job_data.get("confidence_score"),
        transcript_sample=job_data.get("transcript_sample"),
        all_results=job_data.get("all_results"),
        metadata=job_data.get("metadata"),
        async_mode=job_data.get("async_mode", True)
    )

@router.delete("/cleanup/{job_id}", response_model=CleanupResponse)
async def cleanup_detection_job(job_id: str):
    """Delete job files and remove from tracking"""
    if job_id not in detector.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = detector.jobs[job_id]
    files_deleted = []
    
    # Cleanup files
    for file_key in ["video_path", "audio_path", "results_file"]:
        if file_key in job_data:
            file_path = Path(job_data[file_key])
            if file_path.exists():
                file_path.unlink()
                files_deleted.append(str(file_path))
    
    # Remove job from tracking
    del detector.jobs[job_id]
    
    return CleanupResponse(
        job_id=job_id,
        message="Job cleaned up successfully",
        files_deleted=files_deleted
    )

@router.get("/stats", response_model=StatsResponse)
async def get_api_statistics():
    """Get API usage statistics"""
    total_jobs = len(detector.jobs)
    completed = sum(1 for job in detector.jobs.values() if job["status"] == DetectionStatus.COMPLETED)
    processing = sum(1 for job in detector.jobs.values() if job["status"] in [DetectionStatus.DOWNLOADING, 
                                                                             DetectionStatus.EXTRACTING_AUDIO, 
                                                                             DetectionStatus.DETECTING_LANGUAGE])
    failed = sum(1 for job in detector.jobs.values() if job["status"] == DetectionStatus.FAILED)
    pending = sum(1 for job in detector.jobs.values() if job["status"] == DetectionStatus.PENDING)
    
    # Language statistics
    language_counts = {}
    for job in detector.jobs.values():
        if job["status"] == DetectionStatus.COMPLETED and "detected_language" in job:
            lang = job.get("detected_language")
            if lang:
                language_counts[lang] = language_counts.get(lang, 0) + 1
    
    # Async/Sync statistics
    async_jobs = sum(1 for job in detector.jobs.values() if job.get("async_mode", True))
    sync_jobs = total_jobs - async_jobs
    
    stats = {
        "total_jobs": total_jobs,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "pending": pending,
        "async_jobs": async_jobs,
        "sync_jobs": sync_jobs,
        "most_detected_languages": dict(sorted(
            language_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5])
    }
    
    return StatsResponse(**stats)