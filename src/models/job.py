"""Job models and types."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Possible states for a job."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResult(BaseModel):
    """Result of a completed job."""

    url: str
    content: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    """Represents a single page fetch job."""

    id: str
    session_id: str
    url: str
    status: JobStatus = JobStatus.QUEUED
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_ms: int | None = None
    result: JobResult | None = None

    def mark_started(self) -> None:
        """Mark the job as started."""
        self.status = JobStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()

    def mark_completed(self, result: JobResult) -> None:
        """Mark the job as completed with result."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.execution_time_ms = int(delta.total_seconds() * 1000)

    def mark_failed(self, error: str) -> None:
        """Mark the job as failed with error."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.result = JobResult(url=self.url, error=error)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.execution_time_ms = int(delta.total_seconds() * 1000)


class JobResponse(BaseModel):
    """API response model for a job."""

    id: str
    status: JobStatus
    execution_time_ms: int | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: JobResult | None = None
