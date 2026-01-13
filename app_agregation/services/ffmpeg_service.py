"""FFmpeg service for local video processing."""

import subprocess
import os
import logging
from pathlib import Path
from typing import Optional

from config.settings import settings
from utils.exceptions import FFmpegError

logger = logging.getLogger(__name__)


class FFmpegService:
    """Handles FFmpeg operations for video processing."""

    @staticmethod
    def _get_ffmpeg_path(path: Path) -> str:
        """
        Convert a Path object to an FFmpeg-friendly string for the subtitles filter.
        
        FFmpeg's complex filters (like subtitles=filename) require specific escaping:
        1. Backslashes must be forward slashes.
        2. Colons (like in C:/) must be escaped (C\:/).
        3. The whole path should be quoted if it contains spaces.
        """
        # Convert to POSIX style (forward slashes)
        p = path.as_posix()
        
        # Escape the colon (required for Windows drive letters in filters)
        # e.g., "C:/Users" -> "C\:/Users"
        p = p.replace(":", "\\:")
        
        # Wrap in single quotes to handle spaces in path safely
        return f"'{p}'"

    @staticmethod
    def _validate_srt_content(srt_path: Path) -> None:
        """
        Check if the SRT file contains valid subtitle data before burning.
        """
        try:
            with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read just the start of the file to check format
                content = f.read(1024).strip()
            
            if not content:
                raise FFmpegError(f"SRT file is empty: {srt_path.name}")

            # Check for JSON artifacts (if previous parsing failed silently)
            if content.startswith('{') and '"status":' in content:
                raise FFmpegError("SRT file contains JSON data, not subtitle text.")
            
            # Check for HTML (Service Error Pages often return 200 OK with HTML)
            if '<html' in content.lower() or '<!doctype' in content.lower():
                raise FFmpegError("SRT file contains HTML (likely a service error page).")
            
            # Basic SRT validation: Should usually start with a number ('1')
            lines = content.splitlines()
            if lines and not lines[0].strip().isdigit():
                 logger.warning(f"SRT file does not start with a number. Content preview: {lines[0]}")

        except FileNotFoundError:
            raise FFmpegError(f"SRT file missing during validation: {srt_path}")
        except Exception as e:
            if isinstance(e, FFmpegError):
                raise
            logger.warning(f"Skipping strict SRT validation due to read error: {e}")

    @staticmethod
    def burn_subtitles(
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        preset: Optional[str] = None
    ) -> None:
        """
        Burn subtitles into video using FFmpeg.
        
        Args:
            video_path: Path to input video
            srt_path: Path to .srt file
            output_path: Path where burned video will be saved
            preset: FFmpeg compression preset (default: from settings)
        """
        if not video_path.exists():
            raise FFmpegError(f"Video file not found: {video_path}")
        
        # 1. Validate Content
        FFmpegService._validate_srt_content(srt_path)
        
        preset = preset or settings.FFMPEG_PRESET
        
        # 2. Prepare Paths (Absolute & Escaped)
        # We use absolute paths to avoid reliance on relative paths or CWD
        input_file = str(video_path.absolute())
        output_file = str(output_path.absolute())
        
        # Prepare the subtitle path specially for the filter
        # e.g., D:/Temp/file.srt -> 'D\:/Temp/file.srt'
        srt_filter_path = FFmpegService._get_ffmpeg_path(srt_path.absolute())
        
        try:
            # 3. Construct Command
            # -y: Overwrite output
            # -vf subtitles=...: The filter that burns the text
            # -c:a copy: Copy audio stream without re-encoding (faster)
            command = [
                "ffmpeg",
                "-y",
                "-i", input_file,
                "-vf", f"subtitles={srt_filter_path}", 
                "-c:v", settings.FFMPEG_CODEC,
                "-preset", preset,
                "-c:a", "copy",
                output_file
            ]
            
            logger.info(f"Starting FFmpeg burn for: {video_path.name}")
            logger.debug(f"FFmpeg Command: {command}")

            # 4. Execute
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300, # 5 minute timeout for burning
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg Exit Code: {result.returncode}")
                # Log the last 20 lines of stderr for context
                tail_log = '\n'.join(result.stderr.splitlines()[-20:])
                logger.error(f"FFmpeg Log Tail:\n{tail_log}")
                raise FFmpegError(f"FFmpeg processing failed: {tail_log}")
                
            if not output_path.exists():
                raise FFmpegError("Output file missing after FFmpeg run")
                
            logger.info(f"Successfully burned subtitles: {output_path.name}")

        except subprocess.TimeoutExpired:
            raise FFmpegError("FFmpeg process timed out (limit: 300s)")
        except Exception as e:
            if isinstance(e, FFmpegError):
                raise
            raise FFmpegError(f"FFmpeg execution failed: {str(e)}")