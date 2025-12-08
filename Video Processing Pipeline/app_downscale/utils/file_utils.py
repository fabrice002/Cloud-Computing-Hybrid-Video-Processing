from pathlib import Path
from typing import Optional, List
import shutil

def cleanup_files(file_paths: List[str]) -> List[str]:
    """Delete files if they exist"""
    deleted_files = []
    
    for file_path in file_paths:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            deleted_files.append(str(path))
    
    return deleted_files

def get_safe_filename(filename: str) -> str:
    """Convert filename to safe string"""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

def get_file_size_mb(file_path: Path) -> float:
    """Get file size in MB"""
    return round(file_path.stat().st_size / (1024 * 1024), 2)

def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """Check if file extension is allowed"""
    return Path(filename).suffix.lower() in allowed_extensions