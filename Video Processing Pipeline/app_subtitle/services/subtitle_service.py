# app_subtitle/services/subtitle_service.py

import whisper
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from config.settings import Settings
from utils.timestamp_utils import format_srt_timestamp

logger = logging.getLogger(__name__)

class SubtitleService:
    """Service for generating subtitles using Whisper AI."""
    
    def __init__(self):
        self.models: Dict[str, whisper.Whisper] = {}
        self.current_model_name: Optional[str] = None
    
    def load_model(self, model_name: str = Settings.DEFAULT_MODEL) -> None:
        """Load Whisper model into memory."""
        if model_name not in Settings.WHISPER_MODELS:
            raise ValueError(f"Invalid model name. Allowed: {Settings.WHISPER_MODELS}")
        
        if self.current_model_name != model_name:
            logger.info(f"Loading Whisper model: {model_name}")
            self.models[model_name] = whisper.load_model(model_name)
            self.current_model_name = model_name
            logger.info(f"Whisper model '{model_name}' loaded successfully")
    
    def generate_srt(
        self, 
        audio_path: Path, 
        model_name: str = Settings.DEFAULT_MODEL,
        language: Optional[str] = None
    ) -> Path:
        """
        Generate SRT subtitle file from audio using Whisper.
        
        Args:
            audio_path: Path to audio file
            model_name: Whisper model to use
            language: Language code for transcription
            
        Returns:
            Path to generated SRT file
        """
        logger.info(f"Starting transcription with model '{model_name}'")
        
        # Load model if not already loaded
        self.load_model(model_name)
        model = self.models[model_name]
        
        srt_path = Settings.TEMP_DIR / f"{audio_path.stem}_subtitles.srt"
        
        try:
            # Configure transcription options
            transcribe_options: Dict[str, Any] = {
                "word_timestamps": True,
                "verbose": False,
                "task": "transcribe"
            }
            
            if language:
                transcribe_options["language"] = language
            
            # Transcribe audio
            result = model.transcribe(str(audio_path), **transcribe_options)
            
            # Get full text transcription
            full_text = result.get("text", "")
            
            # logger.info(f"Full text transcription: {full_text}")
            
            # Write SRT file
            self._write_srt_file(srt_path, result["segments"])
            
            logger.info(f"Subtitles generated: {srt_path}")
            return srt_path, full_text
            
        except Exception as e:
            logger.error(f"Failed to generate subtitles: {str(e)}")
            raise
    
    def _write_srt_file(self, srt_path: Path, segments: list) -> None:
        """Write segments to SRT file."""
        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, segment in enumerate(segments, start=1):
                start_time = format_srt_timestamp(segment["start"])
                end_time = format_srt_timestamp(segment["end"])
                text = segment["text"].strip()
                
                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
    
    def cleanup_models(self) -> None:
        """Clean up loaded models to free memory."""
        logger.info("Cleaning up Whisper models")
        self.models.clear()
        self.current_model_name = None