#  app_subtitle/routes/subtitle_routes
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
import uuid
from datetime import datetime


from utils.logging_config import logger
from config.settings import Settings
from models.response_models import ProcessingResult, ErrorResponse
from services.video_processor import VideoProcessor
from utils.file_utils import validate_file_extension, save_uploaded_file, cleanup_file

router = APIRouter(prefix="/api", tags=["subtitle"])
processor = VideoProcessor()

@router.post("/generate-subtitles/")
async def generate_subtitles(
    video: UploadFile = File(..., description="Video file to process"),
    model_name: str = Settings.DEFAULT_MODEL,
    language: str = None
):
    """
    Generate and embed subtitles into a video file.
    
    Args:
        video: Uploaded video file
        model_name: Whisper model size (tiny, base, small, medium, large)
        language: Optional language code for transcription
        
    Returns:
        FileResponse with processed video and subtitle file
    """
    # Validate file extension
    if not validate_file_extension(video.filename, Settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(sorted(Settings.ALLOWED_EXTENSIONS))}"
        )
    
    # Create unique filename
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save uploaded video
    video_filename = f"{timestamp}_{unique_id}_{Path(video.filename).name}"
    video_path = Settings.TEMP_DIR / video_filename
    
    try:
        save_uploaded_file(video, video_path)
        logger.info(f"Video uploaded: {video_path}")
        
        # Process video
        output_path, srt_path, full_text = processor.process_video(
            video_path, model_name, language
        )
        
        # Clean up input video (keep subtitles and output)
        cleanup_file(video_path)
        
        # Return both files
        """ response = FileResponse(
            path=srt_path,
            media_type="video/mp4",
            filename=f"subtitled_{Path(video.filename).name}"
        ) """
        
        response = full_text
        
        # Add subtitle file as additional download header
        # response.headers["X-Subtitle-File"] = srt_path.name
        
        return response
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process video: {str(e)}"
        )

@router.get("/download-subtitles/{filename}")
async def download_subtitles(filename: str):
    """
    Download subtitle file.
    
    Args:
        filename: Name of subtitle file to download
    """
    subtitle_path = Settings.OUTPUT_DIR / filename
    
    if not subtitle_path.exists() or not subtitle_path.suffix == '.srt':
        raise HTTPException(
            status_code=404,
            detail="Subtitle file not found"
        )
    
    return FileResponse(
        path=subtitle_path,
        media_type="application/x-subrip",
        filename=subtitle_path.name
    )