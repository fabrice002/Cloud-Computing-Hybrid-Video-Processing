"""Client services for external API calls."""

import httpx
import logging
from pathlib import Path
from typing import Dict, Any, Union

from config.settings import settings
from utils.exceptions import SubtitleServiceError, CompressionServiceError

logger = logging.getLogger(__name__)


class ExternalServices:
    """Handles communication with external microservices."""
    
    @staticmethod
    async def fetch_subtitles(
        client: httpx.AsyncClient,
        video_path: Path,
        original_filename: str,
        model_name: str
    ) -> Path:
        """
        Request subtitles (JSON format) and SAVE them to a local .srt file.
        """
        logger.info(f"Requesting subtitles for: {original_filename} (model: {model_name})")
        
        try:
            with open(video_path, "rb") as video_file:
                # 1. Prepare Request
                # 'files' handles the multipart video upload
                files = {"video": (original_filename, video_file, "video/mp4")}
                
                # 'data' handles the Form fields (model_name, language, output_format)
                # CRITICAL: We request 'json' format to get text back, not a video
                data = {
                    "model_name": model_name,
                    "output_format": "json" 
                }
                
                response = await client.post(
                    settings.SUBTITLE_SERVICE_URL,
                    files=files,
                    data=data,  # Use 'data' for Form fields, not 'params'
                    timeout=settings.SUBTITLE_TIMEOUT
                )
            
            # 2. Handle Errors
            if response.status_code != 200:
                error_detail = response.text[:200]
                logger.error(f"Subtitle service returned {response.status_code}: {error_detail}")
                raise SubtitleServiceError(
                    f"Subtitle service failed with status {response.status_code}: {error_detail}"
                )
            
            # 3. Parse JSON Response
            try:
                response_data = response.json()
                
                # Check for success status if your API returns it
                if response_data.get("status") == "error":
                     raise SubtitleServiceError(f"Subtitle API Error: {response_data.get('detail')}")

                # Extract the raw SRT content
                srt_content = response_data.get("srt_content")
                
                if not srt_content:
                    # Fallback for older API versions or raw text responses
                    logger.warning("Key 'srt_content' not found in response, falling back to raw text check.")
                    srt_content = response_data.get("subtitles") or response.text

            except ValueError:
                # If valid JSON wasn't returned, treat the whole body as the subtitle (fallback)
                logger.warning("Subtitle service did not return JSON. Using raw response body.")
                srt_content = response.text

            # 4. Save to Local File
            # Define path: same folder as video, same name, .srt extension
            srt_path = video_path.with_suffix(".srt")
            
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
                
            logger.info(f"Successfully saved subtitles to: {srt_path.name}")
            return srt_path
            
        except httpx.TimeoutException:
            logger.error("Subtitle service request timed out")
            raise SubtitleServiceError("Subtitle generation timed out")
        except httpx.RequestError as e:
            logger.error(f"Subtitle service connection error: {e}")
            raise SubtitleServiceError(f"Could not connect to subtitle service: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in subtitle fetch: {e}")
            raise SubtitleServiceError(f"Subtitle generation failed: {e}")
    
    @staticmethod
    async def compress_video(
        client: httpx.AsyncClient,
        video_path: Path,
        filename: str,
        resolution: str,
        crf: int
    ) -> str:
        """
        Request video compression from Compression Service.
        """
        logger.info(f"Requesting compression: {filename} (res: {resolution}, crf: {crf})")
        
        try:
            with open(video_path, "rb") as video_file:
                files = {"file": (filename, video_file, "video/mp4")}
                # Use 'data' for Form fields here as well
                data = {
                    "resolution": resolution,
                    "crf_value": str(crf), # Ensure it's a string for Form data
                    "async_mode": "false"
                }
                
                response = await client.post(
                    settings.COMPRESSION_SERVICE_URL,
                    files=files,
                    data=data,
                    timeout=settings.COMPRESSION_TIMEOUT
                )
            
            if response.status_code != 200:
                error_detail = response.text[:200]
                logger.error(f"Compression service returned {response.status_code}: {error_detail}")
                raise CompressionServiceError(
                    f"Compression failed with status {response.status_code}: {error_detail}"
                )
            
            result = response.json()
            # Handle potential different response keys
            output_path_str = result.get('output_path') or result.get('filename')
            
            if not output_path_str:
                raise KeyError("Response missing 'output_path' or 'filename'")
                
            output_filename = Path(output_path_str).name
            logger.info(f"Successfully compressed video: {output_filename}")
            return output_filename
            
        except httpx.TimeoutException:
            logger.error("Compression service request timed out")
            raise CompressionServiceError("Video compression timed out")
        except httpx.RequestError as e:
            logger.error(f"Compression service connection error: {e}")
            raise CompressionServiceError(f"Could not connect to compression service: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Compression service invalid response: {e}")
            raise CompressionServiceError(f"Invalid response from compression service: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in compression: {e}")
            raise CompressionServiceError(f"Video compression failed: {e}")