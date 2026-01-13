import logging
import time
from pathlib import Path
from typing import Tuple, Optional
from contextlib import contextmanager

from config.settings import Settings
from services.subtitle_service import SubtitleService
from services.ffmpeg_service import FFmpegService
from utils.file_utils import cleanup_file, get_file_size_mb

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Main video processing orchestrator."""
    
    def __init__(self, output_dir: Path = Settings.OUTPUT_DIR):
        self.output_dir = output_dir
        self.subtitle_service = SubtitleService()
        self.ffmpeg_service = FFmpegService()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def temporary_files_context(self, *file_paths: Path):
        """
        Context manager to automatically clean up temporary files.
        """
        try:
            yield
        finally:
            for file_path in file_paths:
                if file_path and file_path.exists():
                    cleanup_file(file_path)
    
    def process_video(
        self,
        video_path: Path,
        model_name: str = Settings.DEFAULT_MODEL,
        language: Optional[str] = None,
        burn_subtitles: bool = True  # <--- NEW: Optional flag to skip burning
    ) -> Tuple[Optional[Path], Path, str]:
        """
        Process video: extract audio, generate subtitles, optionally embed subtitles.
        
        Args:
            video_path: Path to input video file
            model_name: Whisper model name
            language: Language code for transcription
            burn_subtitles: If True, burns subtitles into video. If False, skips burning.
            
        Returns:
            Tuple of (output_video_path [Optional], subtitle_file_path, full_text)
        """
        start_time = time.time()
        
        # Validate input file
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        file_size_mb = get_file_size_mb(video_path)
        if file_size_mb > Settings.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File too large: {file_size_mb:.1f}MB > {Settings.MAX_FILE_SIZE_MB}MB"
            )
        
        audio_path = None
        srt_path = None
        output_path = None
        
        try:
            # Step 1: Extract audio
            logger.info("Step 1: Extracting audio")
            audio_path = self.ffmpeg_service.extract_audio(video_path)
            
            # Step 2: Generate subtitles
            logger.info("Step 2: Generating subtitles")
            srt_path, full_text = self.subtitle_service.generate_srt(
                audio_path, model_name, language
            )
            
            # Step 3: Embed subtitles (OPTIONAL)
            if burn_subtitles:
                logger.info("Step 3: Embedding subtitles")
                output_path = self.ffmpeg_service.embed_subtitles(
                    video_path, srt_path, self.output_dir
                )
            else:
                logger.info("Skipping subtitle embedding (requested text/json only)")
                output_path = None
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            logger.info(f"Processing completed in {processing_time:.1f} seconds")
            logger.info(f"Subtitle file: {srt_path}")
            
            return output_path, srt_path, full_text
            
        except Exception as e:
            # Cleanup on error
            logger.error(f"Processing failed: {str(e)}")
            
            # Clean up any created files
            for path in [audio_path, srt_path, output_path]:
                if path and path.exists():
                    cleanup_file(path)
            
            raise
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up video processor resources")
        self.subtitle_service.cleanup_models()