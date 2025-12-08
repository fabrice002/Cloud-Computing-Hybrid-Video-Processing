# app_langscale/services/background_worker.py 

import logging
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile
from services.detector_service import VideoLanguageDetector
from models.enums import DetectionStatus
from utils.constants import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

detector = VideoLanguageDetector()

async def process_detection_job(job_id: str, video_url: str, duration: int, test_all: bool):
    """
    Background task to process language detection from URL
    
    Args:
        job_id: Unique job identifier
        video_url: URL of video to download
        duration: Duration in seconds to analyze
        test_all: Whether to test all supported languages
    """
    try:
        # Update status to processing
        detector.jobs[job_id].update({
            "status": DetectionStatus.PROCESSING,
            "message": "Downloading video..."
        })
        
        # Download video
        video_path = await detector.download_video(video_url, job_id)
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
            test_all
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
        
        logger.info(f"Language detection completed: {job_id}")
        if detection_results["detected"]:
            logger.info(f"🌍 Detected: {detection_results['language']}")
        
    except Exception as e:
        logger.error(f"Job failed: {job_id} - {str(e)}")
        detector.jobs[job_id].update({
            "status": DetectionStatus.FAILED,
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

async def process_local_detection_job(job_id: str, video_path: str, duration: int, test_all: bool):
    """Process local video file language detection"""
    try:
        detector.jobs[job_id].update({
            "status": DetectionStatus.PROCESSING,
            "message": "Extracting audio from local file..."
        })

        video_path = Path(video_path)

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
            duration,
            test_all
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

    except Exception as e:
        detector.jobs[job_id].update({
            "status": DetectionStatus.FAILED,
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

async def process_uploaded_detection_job(job_id: str, file: UploadFile, duration: int, test_all: bool):
    """Process uploaded video file language detection"""
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
            test_all
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
        
        logger.info(f"Uploaded video language detection completed: {job_id}")
        
    except Exception as e:
        logger.error(f"Uploaded job failed: {job_id} - {str(e)}")
        detector.jobs[job_id].update({
            "status": DetectionStatus.FAILED,
            "message": f"Error: {str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })