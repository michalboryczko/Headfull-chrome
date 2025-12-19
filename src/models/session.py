"""Browser session models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SessionStatus(str, Enum):
    """Possible states for a browser session."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionConfig(BaseModel):
    """Configuration for a browser session."""

    delay_between_requests: int = Field(
        default=0, ge=0, description="Delay in seconds between page loads"
    )
    proxy_server: str | None = Field(
        default=None, description="Proxy server URL (e.g., http://proxy:8080)"
    )


class PageJob(BaseModel):
    """Page URL with its associated job ID."""

    url: str
    id: str


class Session(BaseModel):
    """Represents a browser session."""

    id: str
    status: SessionStatus = SessionStatus.CREATED
    config: SessionConfig
    pages: list[PageJob] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Runtime state (not serialized to API response)
    display_num: int | None = None
    devtools_port: int | None = None
    chrome_pid: int | None = None

    model_config = ConfigDict(ser_json_timedelta="iso8601")


class SessionResponse(BaseModel):
    """API response model for a session."""

    id: str
    status: SessionStatus
    pages: list[PageJob]


class ContentRequest(BaseModel):
    """Request to fetch content from multiple pages."""

    pages: list[str] = Field(..., min_length=1, description="List of URLs to fetch")
    config: SessionConfig = Field(default_factory=SessionConfig)


class ContentResponse(BaseModel):
    """Response after creating a content fetch request."""

    id: str
    status: SessionStatus
    pages: list[PageJob]
