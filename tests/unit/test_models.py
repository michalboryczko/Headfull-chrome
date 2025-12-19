"""Tests for data models."""

import uuid
from datetime import UTC, datetime

from src.models import Job, JobStatus, Session, SessionConfig, SessionStatus
from src.models.session import PageJob


def test_job_creation() -> None:
    """Test basic job creation."""
    job = Job(
        id=str(uuid.uuid4()),
        url="https://example.com",
        session_id="session-123",
        queued_at=datetime.now(UTC),
    )

    assert job.url == "https://example.com"
    assert job.session_id == "session-123"
    assert job.status == JobStatus.QUEUED
    assert job.id is not None


def test_session_creation() -> None:
    """Test basic session creation."""
    session = Session(
        id=str(uuid.uuid4()),
        config=SessionConfig(),
        created_at=datetime.now(UTC),
    )

    assert session.status == SessionStatus.CREATED
    assert session.id is not None
    assert session.pages == []


def test_session_config_defaults() -> None:
    """Test session config default values."""
    config = SessionConfig()

    assert config.proxy_server is None
    assert config.delay_between_requests == 0


def test_page_job() -> None:
    """Test PageJob model."""
    page = PageJob(url="https://example.com", id="job-123")

    assert page.url == "https://example.com"
    assert page.id == "job-123"
