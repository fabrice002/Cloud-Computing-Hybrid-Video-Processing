from typing import Dict, Any
from datetime import datetime
import uuid
from models.enums import JobStatus, VideoSourceType

class JobManager:
    """Manages compression jobs"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
    
    def create_job(
        self,
        source_type: VideoSourceType,
        async_mode: bool = True,
        **kwargs
    ) -> str:
        """Create a new compression job"""
        job_id = str(uuid.uuid4())
        
        self.jobs[job_id] = {
            "job_id": job_id,
            "source_type": source_type,
            "status": JobStatus.PENDING,
            "async_mode": async_mode,
            "message": "Job queued for processing",
            "created_at": datetime.now().isoformat(),
            **kwargs
        }
        
        return job_id
    
    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        **kwargs
    ) -> None:
        """Update job status and information"""
        if job_id not in self.jobs:
            raise ValueError(f"Job not found: {job_id}")
        
        self.jobs[job_id].update({
            "status": status,
            "message": message,
            "updated_at": datetime.now().isoformat(),
            **kwargs
        })
    
    def get_job(self, job_id: str) -> Dict:
        """Get job information"""
        if job_id not in self.jobs:
            raise ValueError(f"Job not found: {job_id}")
        return self.jobs[job_id]
    
    def delete_job(self, job_id: str) -> None:
        """Delete job from manager"""
        if job_id in self.jobs:
            del self.jobs[job_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get job statistics including async/sync breakdown"""
        stats = {
            "total": len(self.jobs),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "async_mode": 0,
            "sync_mode": 0,
            "by_source_type": {
                "URL": 0,
                "LOCAL": 0,
                "UPLOAD": 0
            }
        }
        
        for job in self.jobs.values():
            # Count by status
            status = job.get("status")
            if status in stats:
                stats[status] += 1
            
            # Count by async mode
            if job.get("async_mode", True):
                stats["async_mode"] += 1
            else:
                stats["sync_mode"] += 1
            
            # Count by source type
            source_type = job.get("source_type")
            if source_type and source_type.value in stats["by_source_type"]:
                stats["by_source_type"][source_type.value] += 1
        
        return stats