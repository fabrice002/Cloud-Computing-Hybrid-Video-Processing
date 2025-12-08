from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
import os
from config.settings import Settings

router = APIRouter(prefix="/api/videos", tags=["videos"])

@router.get("/{resolution}/{filename}")
async def serve_video(resolution: str, filename: str, request: Request):
    """
    Serve video files from compressed directory
    Example: /api/videos/360p/70116cd8...mp4
    """
    # Security: validate resolution and filename
    if resolution not in Settings.SUPPORTED_RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported resolution: {resolution}")
    
    # Security: prevent path traversal
    if ".." in filename or filename.startswith("/") or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    video_path = Settings.COMPRESSED_DIR / resolution / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Get file size for range requests
    file_size = video_path.stat().st_size
    
    # Check for range header for video streaming
    range_header = request.headers.get("range")
    
    if range_header:
        # Handle range requests (for video seeking)
        return await stream_video_range(video_path, range_header, file_size)
    else:
        # Return full file
        return FileResponse(
            path=video_path,
            media_type="video/mp4",
            filename=filename,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )

async def stream_video_range(video_path: Path, range_header: str, file_size: int):
    """Handle HTTP range requests for video streaming"""
    try:
        range_type, range_spec = range_header.split("=")
        if range_type != "bytes":
            raise HTTPException(status_code=416, detail="Range not satisfiable")
        
        start_str, end_str = range_spec.split("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        
        if start >= file_size or end >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")
        
        content_length = end - start + 1
        
        # Read file chunk
        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        return StreamingResponse(
            iterfile(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=416, detail=f"Range error: {str(e)}")