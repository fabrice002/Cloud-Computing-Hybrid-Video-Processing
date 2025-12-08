from typing import Union

def format_srt_timestamp(seconds: Union[int, float]) -> str:
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    milliseconds = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    
    minutes, secs = divmod(total_seconds, 60)
    hours, mins = divmod(minutes, 60)
    
    return f"{hours:02d}:{mins:02d}:{secs:02d},{milliseconds:03d}"

def seconds_to_hms(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"