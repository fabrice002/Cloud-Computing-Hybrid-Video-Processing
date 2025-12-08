from pathlib import Path
from typing import Dict, Optional
import logging
import time
import json
import shutil
import httpx
from datetime import datetime
from moviepy import VideoFileClip

from fastapi import UploadFile, HTTPException
from config.settings import Settings

logger = logging.getLogger(__name__)

class VideoDownscaler:
    """Professional video compression service"""
    
    def __init__(self):
        self.settings = Settings
    
    async def download_video(self, video_url: str, job_id: str) -> Path:
        """Download video from URL"""
        try:
            logger.info(f"Downloading video from {video_url}")
            
            filename = f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            download_path = self.settings.DOWNLOADS_DIR / filename
            
            async with httpx.AsyncClient(timeout=self.settings.DOWNLOAD_TIMEOUT) as client:
                async with client.stream('GET', video_url) as response:
                    response.raise_for_status()
                    
                    with open(download_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
            
            logger.info(f"Video downloaded: {download_path}")
            return download_path
            
        except httpx.HTTPError as e:
            logger.error(f"Download failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")
    
    def copy_local_video(self, local_path: str, job_id: str) -> Path:
        """Copy local video to working directory"""
        try:
            logger.info(f"Copying local video from {local_path}")
            
            original_filename = Path(local_path).name
            filename = f"{job_id}_{original_filename}"
            copy_path = self.settings.DOWNLOADS_DIR / filename
            
            shutil.copy2(local_path, copy_path)
            
            logger.info(f"Local video copied: {copy_path}")
            return copy_path
            
        except Exception as e:
            logger.error(f"Failed to copy local video: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to copy local video: {str(e)}")
    
    async def save_uploaded_video(self, file: UploadFile, job_id: str) -> Path:
        """Save uploaded video file"""
        try:
            logger.info(f"Saving uploaded video: {file.filename}")
            
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            filename = f"{job_id}_{safe_filename}"
            save_path = self.settings.UPLOADS_DIR / filename
            
            with open(save_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            logger.info(f"Uploaded video saved: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"Failed to save uploaded video: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded video: {str(e)}")
    
    def get_video_metadata(self, clip: VideoFileClip) -> Dict:
        """Extract video metadata"""
        return {
            "duration": round(clip.duration, 2),
            "fps": clip.fps,
            "size": clip.size,
            "original_resolution": f"{clip.size[1]}p",
            "has_audio": clip.audio is not None
        }
    
    def calculate_compression_ratio(self, original_path: Path, compressed_path: Path) -> float:
        """Calculate compression ratio"""
        original_size = original_path.stat().st_size
        compressed_size = compressed_path.stat().st_size
        return compressed_size / original_size if original_size > 0 else 0
    
    def compress_video(
        self,
        input_path: Path,
        resolution: str,
        crf_value: int,
        job_id: str,
        custom_filename: Optional[str] = None
    ) -> Dict:
        """Compress video to specified resolution"""
        start_time = time.time()
        
        if resolution not in self.settings.SUPPORTED_RESOLUTIONS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        
        # Create output directory
        output_dir = self.settings.COMPRESSED_DIR / resolution
        output_dir.mkdir(parents=True, exist_ok=True)
        
        processing_info = {
            "job_id": job_id,
            "input_file": str(input_path),
            "resolution_target": resolution,
            "crf_value": crf_value,
            "timestamp": datetime.now().isoformat()
        }
        
        clip = None
        resized_clip = None
        
        try:
            # Load video
            clip = VideoFileClip(str(input_path))
            
            # Get original metadata
            original_metadata = self.get_video_metadata(clip)
            processing_info["original_metadata"] = original_metadata
            
            # Resize video
            new_height = self.settings.SUPPORTED_RESOLUTIONS[resolution]
            resized_clip = clip.resized(height=new_height)
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if custom_filename:
                safe_name = Path(custom_filename).stem
                safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
                output_filename = f"{job_id}_{safe_name}_{timestamp}.mp4"
            else:
                original_name = input_path.stem
                output_filename = f"{job_id}_{original_name}_{resolution}_{timestamp}.mp4"
            
            output_path = output_dir / output_filename
            
            # Encoding parameters
            write_kwargs = {
                "codec": self.settings.VIDEO_CODEC,
                "preset": self.settings.ENCODING_PRESET,
                "threads": self.settings.THREADS,
                "ffmpeg_params": ["-crf", str(crf_value), "-movflags", "+faststart"]
            }
            
            logger.info(f"Compressing {input_path.name} -> {resolution} (CRF={crf_value})")
            
            # Encode with or without audio
            if clip.audio is not None:
                write_kwargs.update({
                    "audio_codec": self.settings.AUDIO_CODEC,
                    "audio_bitrate": self.settings.AUDIO_BITRATE
                })
                resized_clip.write_videofile(str(output_path), **write_kwargs)
            else:
                resized_clip.write_videofile(str(output_path), audio=False, **write_kwargs)
            
            # Calculate final metrics
            processing_time = time.time() - start_time
            compression_ratio = self.calculate_compression_ratio(input_path, output_path)
            
            processing_info.update({
                "output_file": str(output_path),
                "output_path_relative": str(output_path.relative_to(self.settings.BASE_DIR)),
                "output_path_url": str(output_path.relative_to(self.settings.BASE_DIR)).replace("\\", "/"),
                "processing_time_seconds": round(processing_time, 2),
                "compression_ratio": round(compression_ratio, 3),
                "original_size_mb": round(input_path.stat().st_size / (1024 * 1024), 2),
                "final_size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
                "status": "completed"
            })
            
            # Save metadata
            metadata_file = output_dir / f"{job_id}_metadata_{timestamp}.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(processing_info, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Compression completed: {output_path}")
            logger.info(f"Compression ratio: {compression_ratio:.1%} | Time: {processing_time:.1f}s")
            
            return processing_info
            
        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            logger.error(error_msg)
            raise
        finally:
            # Clean up resources
            if clip is not None:
                clip.close()
            if resized_clip is not None:
                resized_clip.close()