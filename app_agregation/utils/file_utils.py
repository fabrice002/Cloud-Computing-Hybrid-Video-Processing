# app_agregation/utils/file_utils.py

"""File handling utilities."""


import os
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def cleanup_files(paths: List[Path]) -> None:
    """
    Safely remove temporary files.
    
    Args:
        paths: List of file paths to delete
    """
    for path in paths:
        if path and path.exists():
            try:
                os.remove(path)
                logger.info(f"Cleaned up temporary file: {path.name}")
            except OSError as e:
                logger.warning(f"Failed to cleanup {path}: {e}")


def validate_file_size(file_path: Path, max_size: int) -> bool:
    """
    Validate file size against maximum allowed.
    
    Args:
        file_path: Path to the file
        max_size: Maximum allowed size in bytes
        
    Returns:
        True if file is within size limit
    """
    if not file_path.exists():
        return False
    
    file_size = file_path.stat().st_size
    return file_size <= max_size


def generate_safe_filename(base_name: str, extension: str) -> str:
    """
    Generate a sanitized filename.
    
    Args:
        base_name: Base name for the file
        extension: File extension (without dot)
        
    Returns:
        Sanitized filename
    """
    # Remove unsafe characters
    safe_name = "".join(c for c in base_name if c.isalnum() or c in ('-', '_'))
    return f"{safe_name}.{extension}"

def verify_srt_file(srt_path: Path) -> dict:
    """
    Thoroughly verify an SRT file.
    
    Returns:
        Dictionary with verification results
    """
    result = {
        'exists': False,
        'size': 0,
        'readable': False,
        'has_content': False,
        'has_timestamps': False,
        'encoding': 'unknown',
        'line_count': 0
    }
    
    if not srt_path.exists():
        return result
    
    result['exists'] = True
    result['size'] = srt_path.stat().st_size
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            result['readable'] = True
            result['has_content'] = len(content.strip()) > 0
            result['has_timestamps'] = '-->' in content
            result['line_count'] = len(content.split('\n'))
            result['encoding'] = 'utf-8'
    except UnicodeDecodeError:
        try:
            with open(srt_path, 'r', encoding='latin-1') as f:
                content = f.read()
                result['readable'] = True
                result['encoding'] = 'latin-1'
        except:
            result['encoding'] = 'unknown/binary'
    except Exception as e:
        result['error'] = str(e)
    
    return result
