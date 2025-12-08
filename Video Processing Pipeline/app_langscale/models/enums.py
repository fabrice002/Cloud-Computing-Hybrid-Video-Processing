from enum import Enum

class DetectionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    DETECTING_LANGUAGE = "detecting_language"
    COMPLETED = "completed"
    FAILED = "failed"
