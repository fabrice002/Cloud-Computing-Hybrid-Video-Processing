import ffmpeg
import logging
from pathlib import Path
from typing import Optional
import subprocess

logger = logging.getLogger(__name__)

class FFmpegService:
    """Service for video and audio processing using FFmpeg."""
    
    @staticmethod
    def extract_audio(video_path: Path) -> Path:
        """
        Extract audio track from video file.
        
        Args:
            video_path: Path to input video file
            
        Returns:
            Path to extracted audio file
        """
        logger.info(f"Extracting audio from: {video_path}")
        audio_path = video_path.parent / f"{video_path.stem}_audio.wav"
        
        try:
            # Use subprocess for better error handling
            command = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # WAV format
                '-ar', '16000',  # 16kHz sample rate (Whisper optimal)
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                str(audio_path)
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Audio extracted to: {audio_path}")
            return audio_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise ValueError("Failed to extract audio from video")
    
    @staticmethod
    def embed_subtitles(video_path: Path, srt_path: Path, output_dir: Path) -> Path:
        """
        Embed subtitles into video while preserving audio synchronization.
        
        Args:
            video_path: Path to input video
            srt_path: Path to SRT subtitle file
            output_dir: Directory for output file
            
        Returns:
            Path to output video with embedded subtitles
        """
        logger.info("Embedding subtitles into video")
        output_path = output_dir / f"{video_path.stem}_with_subtitles.mp4"
        
        try:
            # Escape the subtitle path for ffmpeg filter
            srt_filter = str(srt_path).replace('\\', '/').replace(':', '\\:')
            
            # Get video duration for validation
            probe = ffmpeg.probe(str(video_path))
            
            # Construct FFmpeg command
            (
                ffmpeg
                .input(str(video_path))
                .output(
                    str(output_path),
                    vf=f"subtitles='{srt_filter}'",
                    acodec='copy',  # Copy audio without re-encoding
                    vcodec='libx264',
                    preset='medium',
                    crf='23',
                    **{'avoid_negative_ts': 'make_zero'}
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Video with subtitles created: {output_path}")
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise ValueError("Failed to embed subtitles into video")
    
    @staticmethod
    def get_video_info(video_path: Path) -> dict:
        """Get video metadata using FFprobe."""
        try:
            probe = ffmpeg.probe(str(video_path))
            return probe
        except ffmpeg.Error as e:
            logger.error(f"FFprobe error: {e.stderr.decode()}")
            raise ValueError("Failed to get video information")