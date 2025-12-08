from enum import Enum

class ResolutionEnum(str, Enum):
    """Supported video resolutions"""
    R1080P = "1080p"
    R720P = "720p"
    R480P = "480p"
    R360P = "360p"
    R240P = "240p"

class VideoSourceType(str, Enum):
    """Video source types"""
    URL = "url"
    LOCAL = "local"
    UPLOAD = "upload"

class JobStatus(str, Enum):
    """Job status types"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"