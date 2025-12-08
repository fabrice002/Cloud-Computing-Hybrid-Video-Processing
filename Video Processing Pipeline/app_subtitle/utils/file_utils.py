import shutil
from pathlib import Path
from typing import List, Set
import logging

logger = logging.getLogger(__name__)

def cleanup_file(file_path: Path) -> None:
    """Remove file if it exists."""
    try:
        if file_path and file_path.exists():
            file_path.unlink()
            logger.debug(f"Cleaned up: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup {file_path}: {str(e)}")

def cleanup_files(file_paths: List[Path]) -> None:
    """Remove multiple files."""
    for file_path in file_paths:
        cleanup_file(file_path)

def get_file_size_mb(file_path: Path) -> float:
    """Get file size in MB."""
    return file_path.stat().st_size / (1024 * 1024)

def validate_file_extension(filename: str, allowed_extensions: Set[str]) -> bool:
    """Check if file extension is allowed."""
    return Path(filename).suffix.lower() in allowed_extensions

def save_uploaded_file(uploaded_file, save_path: Path) -> None:
    """Save uploaded file to disk."""
    with open(save_path, "wb") as f:
        content = uploaded_file.file.read()
        f.write(content)