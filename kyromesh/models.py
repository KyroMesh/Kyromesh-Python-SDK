"""Data models for Kyromesh SDK."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class Job:
    """Represents an AI job in Kyromesh."""
    
    id: str
    status: str  # "pending", "running", "completed", "failed"
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    cost: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_ms: Optional[int] = None
    retry_count: int = 0
    
    def is_completed(self) -> bool:
        """Check if job has completed (success or failure)."""
        return self.status in ("completed", "failed")
    
    def is_successful(self) -> bool:
        """Check if job completed successfully."""
        return self.status == "completed"


@dataclass
class Batch:
    """Represents a batch of jobs in Kyromesh."""
    
    id: str
    status: str  # "processing", "completed", "failed"
    total_jobs: int
    done_jobs: int
    failed_jobs: int
    job_ids: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def is_completed(self) -> bool:
        """Check if batch has completed."""
        return self.status in ("completed", "failed")
    
    def progress_percentage(self) -> float:
        """Get batch completion percentage."""
        if self.total_jobs == 0:
            return 0.0
        return ((self.done_jobs + self.failed_jobs) / self.total_jobs) * 100


@dataclass
class Usage:
    """Represents usage metrics for a workspace."""
    
    jobs_used: int
    jobs_limit: int
    jobs_remaining: int
    overage_jobs: int
    total_cost: float
    tier: str
    overage_rate: float
    
    def usage_percentage(self) -> float:
        """Get usage percentage."""
        if self.jobs_limit == 0:
            return 0.0
        return (self.jobs_used / self.jobs_limit) * 100
