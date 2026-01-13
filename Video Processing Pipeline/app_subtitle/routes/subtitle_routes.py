from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import uuid
from datetime import datetime
from typing import Optional

from utils.logging_config import logger
from config.settings import Settings
from services.video_processor import VideoProcessor
from utils.file_utils import validate_file_extension, save_uploaded_file, cleanup_file

router = APIRouter(prefix="/api", tags=["subtitle"])
processor = VideoProcessor()

@router.post("/generate-subtitles/")
async def generate_subtitles(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="Video file to process"),
    model_name: str = Form(Settings.DEFAULT_MODEL),
    language: Optional[str] = Form(None),
    output_format: str = Form("video", description="Format: 'video' (burned) or 'json' (text only)")
):
    """
    Generate subtitles. 
    - output_format='video': Returns video with burned subtitles.
    - output_format='json': Returns JSON with SRT content (for aggregation service).
    """
    # 1. Validate file extension
    if not validate_file_extension(video.filename, Settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(sorted(Settings.ALLOWED_EXTENSIONS))}"
        )
    
    # 2. Setup paths
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"{timestamp}_{unique_id}_{Path(video.filename).name}"
    video_path = Settings.TEMP_DIR / video_filename
    
    try:
        save_uploaded_file(video, video_path)
        logger.info(f"Video uploaded: {video_path}")
        
        # 3. Determine if we need to burn subtitles
        # If the aggregator asks for JSON, we DON'T need to burn the video here.
        should_burn = (output_format == "video")
        
        # 4. Process video
        # NOTE: Ensure your VideoProcessor.process_video accepts the 'burn_subtitles' arg
        output_path, srt_path, full_text = processor.process_video(
            video_path, model_name, language, burn_subtitles=should_burn
        )
        
        # =========================================================
        # OPTION A: RETURN JSON (Text Subtitles for Aggregator)
        # =========================================================
        if output_format == "json":
            # Read the SRT file content into a string
            srt_content = ""
            if srt_path and srt_path.exists():
                with open(srt_path, "r", encoding="utf-8") as f:
                    srt_content = f.read()
            
            # Clean up all temp files immediately since we are done
            cleanup_file(video_path)
            cleanup_file(srt_path)
            if output_path: cleanup_file(output_path)
            
            return JSONResponse(content={
                "status": "success",
                "filename": video.filename,
                "srt_content": srt_content,  # <--- This is what the Aggregator needs
                "full_text": full_text
            })

        # =========================================================
        # OPTION B: RETURN VIDEO (Direct Download)
        # =========================================================
        elif output_path and output_path.exists():
            # Schedule cleanup for after the file is sent
            background_tasks.add_task(cleanup_file, video_path)
            background_tasks.add_task(cleanup_file, srt_path)
            # output_path is NOT cleaned immediately so user can download it.
            # Ideally, have a cron job to clean output_dir periodically.
            
            return FileResponse(
                path=output_path,
                media_type="video/mp4",
                filename=f"subtitled_{Path(video.filename).name}",
                headers={"X-Subtitle-File": srt_path.name}
            )
            
        else:
            raise HTTPException(status_code=500, detail="Failed to generate output file")
            
    except Exception as e:
        cleanup_file(video_path)
        logger.error(f"Processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep the download route as is
@router.get("/download-subtitles/{filename}")
async def download_subtitles(filename: str):
    subtitle_path = Settings.OUTPUT_DIR / filename
    if not subtitle_path.exists() or not subtitle_path.suffix == '.srt':
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    return FileResponse(path=subtitle_path, media_type="application/x-subrip", filename=subtitle_path.name)